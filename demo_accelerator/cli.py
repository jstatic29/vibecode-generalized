"""Local generation never authenticates; Fabric writes require separate approved commands."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .artifacts import generate, scenario_contract
from .config import DemoError, SCENARIOS, example, load
from .fabric import Client, deploy_data, preflight
from .state import REQUIRED_CHECKS, approve, complete, initialize, locked, read


def parser():
    result = argparse.ArgumentParser(prog="fabric-demo")
    commands = result.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Write an intake template; no network calls")
    init.add_argument("--scenario", choices=SCENARIOS, default="healthcare-access")
    init.add_argument("--output", required=True, type=Path)
    plan = commands.add_parser("plan", help="Validate and preview scenario; no writes to Fabric")
    plan.add_argument("config", type=Path)
    build = commands.add_parser("generate", help="Generate an immutable local run")
    build.add_argument("config", type=Path)
    build.add_argument("--run-dir", required=True, type=Path)
    for name in ("status", "preflight", "deploy-data", "evidence-template", "approve", "complete"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--run-dir", required=True, type=Path)
        if name in {"approve", "complete", "evidence-template"}:
            cmd.add_argument("--gate", required=True)
        if name == "approve":
            cmd.add_argument("--note", required=True)
        if name == "complete":
            cmd.add_argument("--evidence", required=True, type=Path)
        if name == "deploy-data":
            cmd.add_argument("--timeout", type=int, default=1800)
    return result


def execute(args):
    if args.command == "init":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(example(args.scenario), stream, indent=2)
            stream.write("\n")
        return {"intake": str(args.output), "next": "Edit customer, sources, research and approved target"}
    if args.command == "plan":
        config = load(args.config)
        return {"contract": scenario_contract(config), "delta_tables": 17,
                "runtime": "Target 2-4 hours for a guided demo run after prerequisites; not benchmarked",
                "automated": ["local work-package generation", "approved data notebook submission/monitoring"],
                "specialist_assisted": ["website research", "ontology/graph", "data agent", "Rayfin app",
                                       "optional semantic model", "optional Planning"],
                "fabric_writes": False}
    if args.command == "generate":
        config = load(args.config)
        args.run_dir.mkdir(parents=True, exist_ok=False)
        expected = generate(config, args.run_dir)
        state = initialize(args.run_dir, config)
        return {"run_dir": str(args.run_dir), "config_hash": state["config_hash"],
                "gates": list(state["gates"]), "expected": expected,
                "next": "Review OPERATOR.md and approve story; no Fabric writes have occurred"}
    with locked(args.run_dir):
        config, state = read(args.run_dir)
        if args.command == "status":
            return {"config_hash": state["config_hash"], "gates": state["gates"],
                    "resources": state["resources"],
                    "demo_ready": all(g["status"] == "complete" for g in state["gates"].values())}
        if args.command == "evidence-template":
            if args.gate not in state["gates"] or args.gate not in REQUIRED_CHECKS:
                raise DemoError("Unknown, disabled or machine-only gate")
            return {"config_hash": state["config_hash"], "notes": "",
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
            return {"workspace": preflight(config, Client()), "fabric_writes": False,
                    "remaining": "Operator must confirm IQ/Rayfin/Planning feature availability and permissions"}
        if args.command == "deploy-data":
            if args.timeout < 0:
                raise DemoError("timeout must be nonnegative")
            return deploy_data(args.run_dir, args.timeout)
    raise DemoError("Unrecognized command")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = execute(args)
    except (DemoError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0
