"""Local generation never authenticates; Fabric writes require separate approved commands."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .artifacts import generate, scenario_contract
from .config import DemoError, SCENARIOS, brief, example, existing_mode, load
from .discovery import research_brief
from .fabric import Client, deploy_data, preflight
from .state import REQUIRED_CHECKS, approve, complete, initialize, locked, read


def parser():
    result = argparse.ArgumentParser(prog="fabric-demo")
    commands = result.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Write an intake template; no network calls")
    init.add_argument("--scenario", choices=SCENARIOS,
                      help="Optional legacy regression example; omit for an industry-independent brief")
    init.add_argument("--output", required=True, type=Path)
    init.add_argument("--data-mode", choices=["synthetic", "existing-lakehouse"], default="synthetic")
    prereqs = commands.add_parser(
        "check-prereqs", help="Read-only tooling/Azure checks and pending Copilot checks; no run required")
    prereqs.add_argument("--workspace", help="Optional explicitly selected existing workspace name")
    prereqs.add_argument("--data-mode", choices=["synthetic", "existing-lakehouse"])
    prereqs.add_argument("--semantic-model", action="store_true")
    prereqs.add_argument("--app", action="store_true")
    prereqs.add_argument("--fabriciq", action="store_true", help="Require Power BI consumption MCP checks")
    prereqs.add_argument("--output", type=Path, help="Optional new sanitized JSON report; never overwritten")
    usage_template = commands.add_parser(
        "pilot-usage-template", help="Write a private usage worksheet; no network calls")
    usage_template.add_argument("--output", required=True, type=Path)
    usage_report = commands.add_parser(
        "pilot-usage-report", help="Summarize operator-supplied credits and CU usage; no network calls")
    usage_report.add_argument("usage", type=Path)
    usage_report.add_argument("--output", required=True, type=Path)
    copilot_usage = commands.add_parser(
        "pilot-copilot-usage", help="Read native session AI credits without a model call")
    source = copilot_usage.add_mutually_exclusive_group(required=True)
    source.add_argument("--session-dir", type=Path)
    source.add_argument("--usage-file", type=Path)
    copilot_usage.add_argument("--session-ref", help="Required for a native usage export")
    copilot_usage.add_argument("--output", required=True, type=Path)
    plan = commands.add_parser("plan", help="Validate and preview scenario; no writes to Fabric")
    plan.add_argument("config", type=Path)
    build = commands.add_parser("generate", help="Generate an immutable local run")
    build.add_argument("config", type=Path)
    build.add_argument("--run-dir", required=True, type=Path)
    for name in ("status", "preflight", "deploy-data", "setup-lakehouse", "inspect-shortcuts",
                 "sql-preflight", "sql-plan", "approve-sql-plan", "run-sql-plan",
                 "evidence-template", "approve", "complete"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--run-dir", required=True, type=Path)
        if name == "sql-preflight":
            cmd.add_argument("--expected-login", required=True)
        if name in {"sql-plan", "approve-sql-plan", "run-sql-plan"}:
            cmd.add_argument("--plan", required=True, type=Path)
        if name == "approve-sql-plan":
            cmd.add_argument("--note", required=True)
        if name in {"approve", "complete", "evidence-template"}:
            cmd.add_argument("--gate", required=True)
        if name == "approve":
            cmd.add_argument("--note", required=True)
        if name == "complete":
            cmd.add_argument("--evidence", required=True, type=Path)
        if name in {"deploy-data", "setup-lakehouse"}:
            cmd.add_argument("--timeout", type=int, default=1800)
    return result


def execute(args):
    if args.command == "check-prereqs":
        from .prerequisites import check
        result = check(args.workspace, args.data_mode, args.semantic_model, args.app, args.fabriciq)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2)
                stream.write("\n")
        return result
    if args.command in {"pilot-usage-template", "pilot-usage-report", "pilot-copilot-usage"}:
        from .pilot_usage import summarize, template
        if args.command == "pilot-copilot-usage":
            from .copilot_usage import read_export, read_session
            if args.usage_file:
                if not args.session_ref or not args.session_ref.strip():
                    raise DemoError("--session-ref is required with --usage-file")
                result = read_export(args.usage_file, args.session_ref)
            else:
                result = read_session(args.session_dir)
        else:
            result = (template() if args.command == "pilot-usage-template" else
                      summarize(json.loads(args.usage.read_text(encoding="utf-8-sig"), parse_float=str)))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        if args.command == "pilot-copilot-usage":
            return {"output": str(args.output), "network_calls": False,
                    "ai_credits_status": result["ai_credits_status"],
                    "reported_ai_credits": result["reported_ai_credits"],
                    "last_accounted_at": result["last_accounted_at"]}
        return {"output": str(args.output), "network_calls": False,
                "kind": "operator-supplied usage worksheet" if args.command == "pilot-usage-template"
                        else "usage summary and optional allocation estimate; not a bill"}
    if args.command == "init":
        if args.scenario and args.data_mode != "synthetic":
            raise DemoError("Legacy scenarios cannot use existing-lakehouse mode")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(example(args.scenario) if args.scenario else brief(args.data_mode), stream, indent=2)
            stream.write("\n")
        return {"intake": str(args.output), "next": "Edit customer, sources, research and approved target"}
    if args.command == "plan":
        config = load(args.config)
        if existing_mode(config):
            from .existing_data import plan
            return plan(config)
        if config["version"] == 2 and config.get("proposal") is None:
            return research_brief(config)
        if config["version"] == 2:
            from .flexible_data import build_blueprint
            tables, expected = build_blueprint(config)
            workload = {"delta_tables": len(tables) + 2, "physical_rows": expected["physical_rows"],
                        "raw_extracts": expected["raw_extract_count"]}
        else:
            from .data import build_data
            tables, _ = build_data(dict(config, scenario_resources=SCENARIOS[config["scenario"]]["resources"]))
            workload = {"delta_tables": len(tables) + 2}
        return {"contract": scenario_contract(config), **workload,
                "runtime": "Target 2-4 hours for a guided demo run after prerequisites; not benchmarked",
                "automated": ["local work-package generation", "approved data notebook submission/monitoring"],
                "specialist_assisted": ["website research", "ontology/graph", "data agent", "Rayfin app",
                                       "optional semantic model", "optional Planning"],
                "fabric_writes": False}
    if args.command == "generate":
        config = load(args.config)
        if existing_mode(config):
            from .existing_data import require_tables
            require_tables(config)
        args.run_dir.mkdir(parents=True, exist_ok=False)
        expected = generate(config, args.run_dir)
        state = initialize(args.run_dir, config)
        return {"run_dir": str(args.run_dir), "config_hash": state["config_hash"],
                "gates": list(state["gates"]), "expected": expected,
                "next": ("Review OPERATOR.md and approve lakehouse-setup; no Fabric writes have occurred"
                         if existing_mode(config) else
                         "Review OPERATOR.md and approve story; no Fabric writes have occurred")}
    with locked(args.run_dir):
        config, state = read(args.run_dir)
        if args.command == "status":
            return {"config_hash": state["config_hash"], "gates": state["gates"],
                    "resources": state["resources"],
                    "demo_ready": all(g["status"] == "complete" for g in state["gates"].values())}
        if args.command in {"sql-preflight", "sql-plan", "approve-sql-plan", "run-sql-plan"}:
            from .sql_runner import approve_plan, preview, run
            if args.command == "sql-preflight":
                return run(args.run_dir, expected_login=args.expected_login)
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
            if args.command == "sql-plan":
                return preview(args.run_dir, plan)
            if args.command == "approve-sql-plan":
                return approve_plan(args.run_dir, plan, args.note)
            return run(args.run_dir, plan=plan)
        if args.command == "evidence-template":
            if args.gate not in state["gates"] or args.gate not in REQUIRED_CHECKS:
                raise DemoError("Unknown, disabled or machine-only gate")
            extra = {}
            if existing_mode(config):
                from .existing_data import evidence_fields
                extra = evidence_fields(config, args.gate)
                if "destination" in extra:
                    extra["destination"] = {key: state["resources"].get(key)
                                            for key in extra["destination"]}
                if args.gate == "shortcuts":
                    extra["inventory_sha256"] = state["resources"].get(
                        "shortcut_inventory", {}).get("sha256")
            return {"config_hash": state["config_hash"], "notes": "", **extra,
                    "references": [], "checks": {key: False for key in REQUIRED_CHECKS[args.gate]}}
        if args.command == "approve":
            approve(args.run_dir, args.gate, args.note)
            return {"gate": args.gate, "status": "approved"}
        if args.command == "complete":
            report = json.loads(args.evidence.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise DemoError("Evidence must be a JSON object")
            complete(args.run_dir, args.gate, report)
            return {"gate": args.gate, "status": "complete", "verification": "operator-attestation"}
        if args.command == "preflight":
            return {"workspace": preflight(config, Client(
                skill="onelake-catalog-cli" if existing_mode(config) else "spark-cli")), "fabric_writes": False,
                    "remaining": "Operator must confirm IQ/Rayfin/Planning feature availability and permissions"}
        if args.command == "deploy-data":
            if args.timeout < 0:
                raise DemoError("timeout must be nonnegative")
            return deploy_data(args.run_dir, args.timeout)
        if args.command == "setup-lakehouse":
            from .existing_data import setup_lakehouse
            if args.timeout < 0:
                raise DemoError("timeout must be nonnegative")
            return setup_lakehouse(args.run_dir, args.timeout)
        if args.command == "inspect-shortcuts":
            from .existing_data import inspect_shortcuts
            return inspect_shortcuts(args.run_dir)
    raise DemoError("Unrecognized command")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = execute(args)
    except (DemoError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    if args.command == "check-prereqs" and result["blocked"]:
        return 1
    return 0
