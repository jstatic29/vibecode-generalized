"""Shortcut-only existing-data work packages; never generate or mutate source data."""

import hashlib
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import DemoError, _keys, _text, validate_common


def validate_existing(config):
    from .blueprint import identifier

    _keys(config.get("scope"), ["max_query_seconds", "max_result_rows",
                               "baseline_max_age_hours"], "scope")
    validate_common(config)
    for key, upper in (("max_query_seconds", 300), ("max_result_rows", 1000),
                       ("baseline_max_age_hours", 168)):
        value = config["scope"].get(key)
        if type(value) is not int or not 1 <= value <= upper:
            raise DemoError(f"scope.{key} must be an integer from 1 to {upper}")
    _keys(config.get("existing_data"), ["tables"], "existing_data")
    tables = config["existing_data"].get("tables")
    if not isinstance(tables, list):
        raise DemoError("existing_data.tables must be a list of approved shortcut aliases and purposes")
    seen = set()
    for table in tables:
        _keys(table, ["name", "purpose"], "shortcut table")
        name = identifier(table.get("name"), "shortcut table.name")
        if name in seen:
            raise DemoError(f"Duplicate shortcut alias: {name}")
        seen.add(name)
        _text(table.get("purpose"), f"{name}.purpose", 1000)
    if config.get("proposal") is not None:
        raise DemoError("Existing data uses an assessed model in data-readiness evidence, "
                        "not a synthetic proposal or generator recipes")
    return config


def require_tables(config):
    if not config["existing_data"]["tables"]:
        raise DemoError("Select table shortcut aliases/purposes in existing_data.tables before generation")


def plan(config):
    return {
        "data_mode": "existing-lakehouse", "fabric_writes": False,
        "customer": config["customer"], "audience": config["audience"],
        "sources": config["sources"], "features": config["features"],
        "target": config["deployment"], "approved_shortcut_tables": config["existing_data"]["tables"],
        "assessment_limits": config["scope"],
        "research": config.get("research", {}),
        "discovery": [
            "Research public website pages and cite them; distinguish facts from inferred use cases.",
            "Suggest 2-3 audience-relevant use cases and ask for selection before generation. "
            "Record research notes/citations and industry confirmation in the immutable intake.",
            "Copilot helps the operator select shortcut aliases/purposes; no schema or generator code required.",
            "Final model/metrics follow actual assessment. Missing data is a disclosed gap, "
            "not invented records or an automatic switch to synthetic mode.",
        ],
        "sequence": ["approve lakehouse-setup", "setup-lakehouse creates a dedicated lakehouse",
                     "operator manually creates individual table shortcuts",
                     "complete shortcuts gate with effective read-only permission evidence",
                     "approve data-readiness before metadata/aggregate assessment",
                     "approve story/design from assessed model", "continue specialist IQ/model/app phases"],
        "safety": "Shortcuts are not a read-only security boundary. Verify effective source permissions "
                  "for all execution identities; no source or shortcut-target writes.",
        "assessment": "Specialist-assisted, allowlisted metadata and bounded aggregates only; "
                      "no automatic profiling, source ingestion, raw previews or generated notebooks.",
    }


def generate(config, root, write_json):
    require_tables(config)
    write_json(root / "config.json", config)
    write_json(root / "source-contract.json", plan(config))
    write_json(root / "scenario.json", {
        "customer": config["customer"], "audience": config["audience"],
        "data_mode": "existing-lakehouse", "synthetic": False,
        "deployment": config["deployment"], "features": config["features"],
        "tables": config["existing_data"]["tables"],
        "approved_model_location": "evidence/data-readiness.json: assessment",
        "status": "needs-shortcuts-and-assessment; no inferred keys, relationships or metric baselines",
    })
    schema = config["deployment"]["schema"]
    names = ", ".join("'" + t["name"] + "'" for t in config["existing_data"]["tables"])
    sql = (
        "-- Review and execute only after shortcuts completion and data-readiness approval.\n"
        "-- Metadata only, scoped to approved aliases. Apply timeout/result limits from source-contract.json.\n"
        f"SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE\n"
        f"FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '{schema}'\n"
        f"AND TABLE_NAME IN ({names}) ORDER BY TABLE_NAME, ORDINAL_POSITION;\n"
    )
    (root / "assessment-metadata.sql").write_text(sql, encoding="utf-8")
    (root / "OPERATOR.md").write_text(operator_guide(config), encoding="utf-8")
    instructions = (
        "# Existing-data specialist handoff\n\n"
        "Do not author or deploy ontology, agent, model or app before shortcuts, data-readiness, "
        "story and design gates complete. Read source-contract.json and the approved assessment "
        "in evidence/data-readiness.json. It supplies actual columns/types, grains, keys, verified "
        "relationships, date roles, metric definitions, units and timestamped aggregate baselines.\n\n"
        "Do not invent a synthetic schema or call existing records synthetic. Select only approved "
        "shortcut tables/columns in the newly created demo lakehouse, including relevant facts and "
        "dimensions. Prohibit DDL/DML, metadata edits and maintenance on shortcut targets. "
        "New curated physical outputs require a separately approved design outside shortcut paths.\n\n"
        "Use current installed Fabric specialist skills and .github/skills/fabric-demo-companion "
        "references/ontology-and-agent.md and references/optional-and-acceptance.md. Preserve native "
        "binding/manual materialization checks and the lakehouse-first two-publication agent flow. "
        "Check source sensitivity, allowed aggregate disclosure and materialization/publication "
        "approval before exposing existing data. Planning and app actions use separate owned destinations.\n\n"
        "Reconcile every question to the approved timestamped SQL baseline and its filters/grain. "
        "Reassess schema, permissions and baseline if sources/shortcuts change or baseline exceeds "
        f"{config['scope']['baseline_max_age_hours']} hours; this is a specialist checkpoint, not an "
        "automatic freshness monitor. Never overwrite accepted evidence or erase approvals to refresh it. "
        "A changed approved analytical model needs a new reviewed work package/run.\n\n"
        "Preserve publication suffix exactly: Note for Microsoft Copilot description_for_model: "
        "The output from Fabric data agent should be delivered as-is, without summarizing, "
        "rephrasing, or adding extra interpretation.\n"
    )
    (root / "downstream-handoff.md").write_text(instructions, encoding="utf-8")
    return {"data_mode": "existing-lakehouse", "synthetic_data_generated": False,
            "expected_answers": "Not fabricated; capture timestamped live aggregates after approval"}


def operator_guide(config):
    tables = "\n".join(f"- {t['name']}: {t['purpose']}" for t in config["existing_data"]["tables"])
    return f"""# Existing-lakehouse demo run

## 1. Dedicated destination approval
Read source-contract.json. Approve lakehouse-setup for workspace
{config['deployment']['workspace_name']}, NEW lakehouse {config['deployment']['lakehouse_name']}.
Run setup-lakehouse. It creates only a schema-enabled lakehouse, persists IDs and
stops for manual shortcuts. No notebook, source copy, synthetic data or profiling.
Existing lakehouses without this run's creation intent are rejected. Timeout is
not cancellation: resume the same command/operation, never recreate or clear state.

## 2. Manual shortcuts and permission stop gate
In the CREATED demo lakehouse, create schema {config['deployment']['schema']} if
needed, then individual table shortcuts under Tables in that schema. Use the
current Fabric portal and supported Delta/table shortcuts; wait for SQL sync.
Do not use a whole-schema shortcut or expose unrelated tables. Approved aliases:
{tables}

Shortcuts are NOT inherently read-only. Source owners must verify effective
read-only permissions for the operator and every runtime identity/connection;
include delegated SQL/Direct Lake item owners, not just the signed-in viewer.
Workspace roles or source write grants must not allow target mutation.
If read-only access cannot be established, STOP. Never test this by attempting
a write. Do not edit descriptions, optimize/vacuum, merge, delete or otherwise
write through shortcuts. No automated ACL changes or shortcut creation.
Approve/complete shortcuts with actual source-target mapping, destination IDs,
SQL visibility and source permission references. Approve shortcuts, run
inspect-shortcuts, and copy its inventory_sha256 and each actual target into the
shortcuts evidence template. Inventory is machine evidence of paths only, not ACL
verification. No assessment before this stop gate.

## 3. Read-only data-readiness gate
Approve data-readiness for allowlisted metadata and bounded aggregates only.
Load current SQL/OneLake specialist guidance. Review assessment-metadata.sql.
Enforce query timeout {config['scope']['max_query_seconds']} seconds and result
limit {config['scope']['max_result_rows']} rows; limits do not bound scanned rows,
so agree table/partition/time-window scan budgets before running aggregates.
No SELECT *, record sampling, exports of customer rows or automatic profiling.
Sensitive aggregates can still disclose data; get owner approval and suppress them.

Optional execution route: with explicit operator opt-in, use the toolkit's ODBC
runner when the specialist MCP cannot enforce this timeout. sql-preflight checks
identity only after shortcuts completion. Prepare a structured plan outside this
immutable run, preview with sql-plan, then obtain data-readiness AND exact-plan/
scan/disclosure approval before approve-sql-plan and run-sql-plan. Every command
takes --run-dir; plan commands take --plan. Requires ODBC Driver 18 and optional
.[sql]. Only column metadata and single-table aggregates are supported; no
arbitrary SQL, raw rows, grouping or joins. It saves machine receipts and checks
identity/target drift; no automatic readiness completion or retries. Timeout is
per statement and does not prove remote cancellation. See README for plan fields.

Record per-table columns/types, grain, key/null/duplicate findings, relationships
(including orphan checks), date coverage/roles, units, sensitivity and limitations.
Do not assume lakehouse constraints are enforced or invent missing dimensions.
Agree scenario/metric semantics with owner and capture read-only aggregate baselines
with query references, observation time, filters, source versions or drift limitations.
Use evidence-template for the exact report structure. Complete only after readiness
checks pass. Failed quality or permission checks block, not silently clean source data.

## 4. Story/design then common IQ/model/app workflow
Review website research, audience fit and the ASSESSED analytical model; approve
story/design with evidence. Read downstream-handoff.md and current companion
phase references; existing-data outputs are specialist handoffs, NOT API definitions.
Use the created lakehouse shortcuts, not a direct attachment to the source item.
No synthetic notebook or deploy-data on this path. Any curated output must be
separately approved; never place it at shortcut paths. Graph materialization, model refresh,
agent publication and app exposure can copy/expose data and need sensitivity review.

## 5. Freshness, acceptance and recovery
Baseline maximum age: {config['scope']['baseline_max_age_hours']} hours. Recheck
before downstream publication/rehearsal and if schema, target mapping, permissions
or source data changes. The CLI checks age when accepting data-readiness evidence;
ongoing freshness and consistent source snapshots are specialist/operator checks.
Do not claim deterministic synthetic expectations or point-in-time consistency
across live source tables without evidence. Preserve prior reports and record new
timestamped reconciliation outside the immutable run.
Use existing status/evidence-template/approve/complete gates. Complete records owner
attestation, not automatic source verification. Local tests are not Fabric validation.
"""


def evidence_fields(config, gate):
    names = [t["name"] for t in config["existing_data"]["tables"]]
    target = {"workspace_id": None, "lakehouse_id": None}
    if gate == "shortcuts":
        return {"destination": target, "bindings": [
            {"table": name, "source_reference": "", "permission_reference": "",
             "target": None, "read_only_verified": False} for name in names]}
    if gate == "data-readiness":
        return {"destination": target, "assessment": {
            "observed_at": None, "business_question": "", "sensitivity_and_disclosure": "",
            "scan_budget": "", "drift_policy": "",
            "tables": [{"name": name, "columns_and_types": "", "grain": "",
                        "key_findings": "", "relationship_findings": "",
                        "date_coverage_and_roles": "", "limitations": ""} for name in names],
            "metrics": [{"name": "", "definition": "", "unit": "", "grain_and_filters": "",
                         "baseline_value": None, "query_reference": ""}],
        }}
    return {}


def validate_evidence(config, state, gate, report, root):
    if gate not in {"shortcuts", "data-readiness"}:
        return
    _keys(report, ["config_hash", "notes", "references", "checks", "kind", "recorded_at",
                   "destination"] + (["bindings", "inventory_sha256"] if gate == "shortcuts"
                                    else ["assessment"]), f"{gate} evidence")
    expected_target = {"workspace_id": state["resources"].get("workspace_id"),
                       "lakehouse_id": state["resources"].get("lakehouse_id")}
    if not all(expected_target.values()) or report.get("destination") != expected_target:
        raise DemoError("Evidence destination must match this run's created demo lakehouse")
    names = {t["name"] for t in config["existing_data"]["tables"]}
    if gate == "shortcuts":
        inventory = state["resources"].get("shortcut_inventory")
        if not inventory or report.get("inventory_sha256") != inventory["sha256"]:
            raise DemoError("Run inspect-shortcuts and bind this report to its inventory_sha256")
        observed = json.loads((Path(root) / inventory["evidence"]).read_text(encoding="utf-8"))
        targets = {row["table"]: row["target"] for row in observed["bindings"]}
        rows = report.get("bindings")
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise DemoError("Shortcut evidence needs bindings")
        if (len(rows) != len(names) or not all(isinstance(r.get("table"), str) for r in rows)
                or {r.get("table") for r in rows} != names):
            raise DemoError("Shortcut bindings must exactly cover approved table aliases")
        for row in rows:
            _keys(row, ["table", "source_reference", "permission_reference", "target",
                        "read_only_verified"], "shortcut binding")
            if row.get("target") != targets[row["table"]]:
                raise DemoError("Binding target must exactly match the inspected OneLake target")
            for field in ("source_reference", "permission_reference"):
                _text(row.get(field), f"binding.{field}", 2000)
            if row.get("read_only_verified") is not True:
                raise DemoError("Every binding needs effective read-only permission verification")
        return
    assessment = report.get("assessment")
    if not isinstance(assessment, dict):
        raise DemoError("Data-readiness evidence needs an assessment")
    _keys(assessment, ["observed_at", "business_question", "sensitivity_and_disclosure",
                      "scan_budget", "drift_policy", "tables", "metrics"], "assessment")
    try:
        observed = datetime.fromisoformat(assessment["observed_at"].replace("Z", "+00:00"))
        approved = datetime.fromisoformat(state["gates"][gate]["approved_at"])
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        if (observed.tzinfo is None or observed < approved or age < 0
                or age > config["scope"]["baseline_max_age_hours"] * 3600):
            raise ValueError("Stale, future, preapproval or timezone-free observation")
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise DemoError("assessment.observed_at must be a recent timezone-qualified ISO timestamp "
                        "after data-readiness approval") from exc
    for field in ("business_question", "sensitivity_and_disclosure", "scan_budget", "drift_policy"):
        _text(assessment.get(field), f"assessment.{field}", 4000)
    rows = assessment.get("tables")
    if (not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows)
            or not all(isinstance(r.get("name"), str) for r in rows)
            or len(rows) != len(names) or {r.get("name") for r in rows} != names):
        raise DemoError("Assessment must exactly cover approved shortcut tables")
    for row in rows:
        _keys(row, ["name", "columns_and_types", "grain", "key_findings",
                    "relationship_findings", "date_coverage_and_roles", "limitations"], "assessed table")
        for field in ("columns_and_types", "grain", "key_findings", "relationship_findings",
                      "date_coverage_and_roles", "limitations"):
            _text(row.get(field), f"assessment.table.{field}", 8000)
    metrics = assessment.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise DemoError("Assessment needs approved metric definitions and observed baselines")
    seen = set()
    for metric in metrics:
        _keys(metric, ["name", "definition", "unit", "grain_and_filters",
                       "query_reference", "baseline_value"], "assessed metric")
        for field in ("name", "definition", "unit", "grain_and_filters", "query_reference"):
            _text(metric.get(field), f"assessment.metric.{field}", 4000)
        if metric["name"] in seen:
            raise DemoError("Assessment metric names must be unique")
        seen.add(metric["name"])
        if "baseline_value" not in metric:
            raise DemoError("Metric baseline_value is required; null must be explained in definition")
        value = metric["baseline_value"]
        if value is not None and (type(value) not in (int, float)
                                  or (type(value) is float and not math.isfinite(value))):
            raise DemoError("Metric baseline_value must be a finite numeric aggregate or null, never records")


def setup_lakehouse(root, timeout=1800, client=None):
    from .config import existing_mode
    from .fabric import Client, ensure_item, preflight
    from .state import audit, now, read, require_gate, save

    config, state = read(root)
    if not existing_mode(config):
        raise DemoError("setup-lakehouse requires existing-lakehouse mode")
    done = state["gates"]["lakehouse-setup"]["status"] == "complete"
    if not done:
        require_gate(state, "lakehouse-setup", approved=True)
    client = client or Client(skill="onelake-catalog-cli")
    workspace = preflight(config, client)
    wid = workspace["id"]
    resources = state["resources"]
    if resources.get("workspace_id") and resources["workspace_id"] != wid:
        raise DemoError("Workspace identity changed; refusing a new destination")
    resources["workspace_id"] = wid
    save(Path(root) / "state.json", state)
    lakehouse = ensure_item(
        client, root, state, wid, "Lakehouse", config["deployment"]["lakehouse_name"],
        {"creationPayload": {"enableSchemas": True}}, timeout, require_new=True,
    )
    if not done:
        state["gates"]["lakehouse-setup"].update(
            status="complete", completed_at=now(), verification="created-lakehouse-identity-readback")
        audit(root, state, "complete-lakehouse-setup", "lakehouse-setup", lakehouse_id=lakehouse)
    return {"status": "awaiting-manual-shortcuts", "workspace_id": wid, "lakehouse_id": lakehouse,
            "next": "Operator creates individual table shortcuts, verifies source read-only permissions, "
                    "then approves shortcuts and runs inspect-shortcuts; no data was assessed"}


def shortcut_bindings(config, resources, rows):
    """Validate live targets identically during inventory and assessment drift checks."""
    wid, lid = resources["workspace_id"], resources["lakehouse_id"]
    schema = config["deployment"]["schema"]
    names = {t["name"] for t in config["existing_data"]["tables"]}
    bindings = []
    for row in rows:
        if (not isinstance(row, dict) or row.get("path") not in
                (f"Tables/{schema}", f"/Tables/{schema}")
                or not isinstance(row.get("name"), str) or row["name"] not in names):
            raise DemoError("Shortcut inventory includes unapproved paths/tables; review scope in portal")
        target_spec = row.get("target")
        if not isinstance(target_spec, dict) or target_spec.get("type", "OneLake") != "OneLake":
            raise DemoError("Only direct internal OneLake table shortcuts are supported in this path")
        target = target_spec.get("oneLake")
        if not isinstance(target, dict):
            raise DemoError("Only direct internal OneLake table shortcuts are supported in this path")
        try:
            for key in ("workspaceId", "itemId"):
                uuid.UUID(target[key])
            parts = target["path"].split("/")
            if (len(parts) not in (2, 3) or parts[0] != "Tables"
                    or any(not part or part in {".", ".."} or "\\" in part for part in parts)):
                raise ValueError("Not a direct table path")
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            raise DemoError("Shortcut needs a valid OneLake source identity and individual table path") from exc
        if target["workspaceId"] == wid and target["itemId"] == lid:
            raise DemoError("Shortcut cannot target this demo lakehouse itself")
        # Persist only noncredential source identity, never arbitrary connector properties.
        bindings.append({"table": row["name"], "target": {
            key: target[key] for key in ("workspaceId", "itemId", "path")
        }})
    if len(bindings) != len(names) or {r["table"] for r in bindings} != names:
        raise DemoError("Missing or duplicate approved shortcuts; finish manual setup first")
    return sorted(bindings, key=lambda row: row["table"])


def inspect_shortcuts(root, client=None):
    from .config import existing_mode
    from .fabric import Client
    from .state import audit, now, read, require_gate, save

    config, state = read(root)
    if not existing_mode(config):
        raise DemoError("inspect-shortcuts requires existing-lakehouse mode")
    require_gate(state, "shortcuts", approved=True)
    resources = state["resources"]
    wid, lid = resources["workspace_id"], resources["lakehouse_id"]
    client = client or Client(skill="onelake-catalog-cli")
    rows = client.listing(f"/v1/workspaces/{wid}/items/{lid}/shortcuts")
    bindings = shortcut_bindings(config, resources, rows)
    evidence = {"kind": "machine-shortcut-inventory", "observed_at": now(),
                "destination": {"workspace_id": wid, "lakehouse_id": lid},
                "bindings": bindings,
                "permissions_verified": False, "sql_visibility_verified": False}
    relative = f"evidence/shortcut-inventory-{uuid.uuid4().hex}.json"
    path = Path(root) / relative
    path.parent.mkdir(exist_ok=True)
    save(path, evidence)
    resources["shortcut_inventory"] = {
        "evidence": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    audit(root, state, "inspect-shortcuts", "shortcuts", evidence=relative)
    return {**evidence, "inventory_sha256": resources["shortcut_inventory"]["sha256"],
            "next": "Review targets and effective permissions, then complete shortcuts with owner evidence"}
