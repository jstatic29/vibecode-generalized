"""Approval gates are bound to immutable artifact hashes, with an append-only audit."""

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import DemoError, digest, validate


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(root):
    path = Path(root) / ".run.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise DemoError(f"Run is locked: {path}. If its process exited, inspect before removing this file.") from exc
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        yield
    finally:
        path.unlink()


def manifest(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(root).rglob("*")) if p.is_file()
        and p.name not in {"state.json", ".run.lock"}
        and "evidence" not in p.relative_to(root).parts
    }


def initialize(root, config):
    gates = ["story", "design", "data-build", "fabric-iq"]
    if config["features"]["semantic_model"]:
        gates.append("semantic-model")
    if config["features"]["planning"]:
        gates.append("planning")
    if config["features"]["app"]:
        gates.append("app")
    gates.append("rehearsal")
    state = {
        "version": 1, "created_at": now(), "config_hash": digest(config),
        "manifest": manifest(root),
        "gates": {gate: {"status": "pending"} for gate in gates},
        "resources": {}, "audit": [],
    }
    save(Path(root) / "state.json", state)
    return state


def read(root):
    root = Path(root)
    try:
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
        config = validate(json.loads((root / "config.json").read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise DemoError(f"Cannot read run {root}: {exc}") from exc
    if digest(config) != state["config_hash"] or manifest(root) != state["manifest"]:
        raise DemoError("Run artifacts changed after generation. Generate a new run and obtain fresh approvals.")
    for gate, item in state["gates"].items():
        if item.get("evidence"):
            evidence = root / item["evidence"]
            if not evidence.is_file() or hashlib.sha256(evidence.read_bytes()).hexdigest() != item["evidence_sha256"]:
                raise DemoError(f"Evidence changed or disappeared for {gate}")
    return config, state


def require_gate(state, gate, approved=False):
    if gate not in state["gates"]:
        raise DemoError(f"Gate {gate!r} is not enabled for this run")
    for name, item in state["gates"].items():
        if name == gate:
            break
        if item["status"] != "complete":
            raise DemoError(f"Complete prerequisite gate {name!r} first")
    if approved and state["gates"][gate]["status"] != "approved":
        raise DemoError(f"Gate {gate!r} must be explicitly approved before execution")


def audit(root, state, action, gate, **details):
    state["audit"].append({"at": now(), "action": action, "gate": gate, **details})
    save(Path(root) / "state.json", state)


def approve(root, gate, note):
    config, state = read(root)
    require_gate(state, gate)
    if state["gates"][gate]["status"] != "pending":
        raise DemoError(f"{gate} is already {state['gates'][gate]['status']}")
    if not note.strip():
        raise DemoError("An explicit approval note is required")
    if gate == "story" and not config.get("research", {}).get("industry_confirmed"):
        raise DemoError("Research/industry is unconfirmed. Update intake and generate a new run before approval.")
    state["gates"][gate] = {"status": "approved", "approved_at": now(), "note": note}
    audit(root, state, "approve", gate, note=note)


REQUIRED_CHECKS = {
    "story": ["audience_fit", "assumptions_reviewed", "public_sources_reviewed"],
    "design": ["scope_reviewed", "target_approved", "capacity_and_features_reviewed"],
    "fabric-iq": ["sql_endpoint_reconciled", "ontology_readback", "graph_properties_and_edges",
                  "graph_sql_parity", "ontology_attached", "published_agent_smoke"],
    "semantic-model": ["schema_verified", "dax_reconciled", "quarter_filters_verified",
                       "credentials_verified", "viewer_access_verified"],
    "planning": ["model_compatibility_verified", "destination_verified",
                 "write_permissions_verified", "scenario_writeback_readback"],
    "app": ["aggregate_connector_verified", "bundle_parseable", "live_figures_reconciled",
            "signed_in_crud_verified", "server_ownership_verified"],
    "rehearsal": ["headline_verified", "links_verified", "limitations_disclosed", "handoff_ready"],
}


def complete(root, gate, report):
    _, state = read(root)
    require_gate(state, gate, approved=True)
    if gate == "data-build":
        raise DemoError("data-build can only complete from a successful durable notebook job")
    checks = report.get("checks", {})
    if not isinstance(checks, dict):
        raise DemoError("Evidence checks must be an object")
    missing = [key for key in REQUIRED_CHECKS[gate] if checks.get(key) is not True]
    if missing:
        raise DemoError(f"Missing successful checks: {', '.join(missing)}")
    if report.get("config_hash") != state["config_hash"]:
        raise DemoError("Evidence config_hash does not match this run")
    if not isinstance(report.get("notes"), str) or not report["notes"].strip():
        raise DemoError("Evidence needs notes describing what was checked, known issues and artifact locations")
    if not isinstance(report.get("references"), list) or not report["references"]:
        raise DemoError("Evidence needs at least one source, resource link or verification artifact reference")
    if any(not isinstance(ref, str) or not ref.strip() for ref in report["references"]):
        raise DemoError("Evidence references must be nonempty strings")
    evidence = {"kind": "operator-attestation", "recorded_at": now(), **report}
    # Caller cannot disguise an attestation as an automated verification.
    evidence["kind"] = "operator-attestation"
    relative = f"evidence/{gate}.json"
    target = Path(root) / relative
    target.parent.mkdir(exist_ok=True)
    save(target, evidence)
    state["gates"][gate].update(
        status="complete", evidence=relative,
        evidence_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), completed_at=now(),
    )
    audit(root, state, "complete-attested", gate)
