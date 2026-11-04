"""Validate the public intake contract before producing any artifacts."""

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


class DemoError(Exception):
    """An actionable configuration or execution failure."""


SCENARIOS = {
    "healthcare-access": {
        "industry": "Healthcare",
        "event": "transfer request",
        "accepted": "Accepted",
        "declined": "Declined",
        "resources": ["Medical", "ICU", "Surgical", "Emergency"],
        "metric": "Capacity-related transfer declines",
        "question": "Where are capacity-related transfer declines concentrated, and how do "
                    "those regions compare on social risk and uncompensated care?",
        "context": "Social risk screening",
        "finance": "Illustrative uncompensated care at charges, not cost",
    },
    "manufacturing-fulfillment": {
        "industry": "Manufacturing",
        "event": "production order",
        "accepted": "Completed",
        "declined": "Delayed",
        "resources": ["Assembly", "Machining", "Packaging", "Inspection"],
        "metric": "Capacity-related production delays",
        "question": "Where are capacity-related production delays concentrated, and how do "
                    "those regions compare on supplier risk and exception expense?",
        "context": "Supplier risk assessment",
        "finance": "Illustrative exception expense, not lost revenue",
    },
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _keys(value, allowed, label):
    if not isinstance(value, dict):
        raise DemoError(f"{label} must be an object")
    unknown = set(value) - set(allowed)
    if unknown:
        raise DemoError(f"{label}: unknown fields: {', '.join(sorted(unknown))}")


def _text(value, label, maximum=500):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise DemoError(f"{label} must be nonempty text of at most {maximum} characters")
    return value.strip()


def validate_common(value):
    customer = value.get("customer")
    _keys(customer, ["name", "website"], "customer")
    _text(customer.get("name"), "customer.name", 120)
    website = customer.get("website", "")
    parsed = urlparse(website) if isinstance(website, str) else None
    if not parsed or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise DemoError("customer.website must be an HTTPS URL without credentials")
    _text(value.get("audience"), "audience")
    sources = value.get("sources")
    if not isinstance(sources, list) or not sources:
        raise DemoError("sources must contain high-level source descriptions")
    if value["version"] == 1 and len(sources) > 6:
        raise DemoError("Legacy scenarios support at most 6 source descriptions; use a version-2 brief")
    for source in sources:
        _text(source, "source description", 300)
    scope = value.get("scope")
    for key, lower, upper in [
        ("months", 3 if value["version"] == 1 else 1, 24), ("seed", 0, 2147483647),
    ]:
        n = scope.get(key)
        if type(n) is not int or not lower <= n <= upper:
            raise DemoError(f"scope.{key} must be an integer from {lower} to {upper}")
    try:
        end = date.fromisoformat(scope["end_date"])
        if end.isoformat() != scope["end_date"]:
            raise ValueError("Use YYYY-MM-DD")
        if end.year * 12 + end.month - scope["months"] < 12:
            raise ValueError("Date window precedes year 1")
    except (ValueError, KeyError, TypeError) as exc:
        raise DemoError("scope.end_date must be an ISO date (YYYY-MM-DD)") from exc
    features = value.get("features")
    _keys(features, ["semantic_model", "planning", "app"], "features")
    for key in ("semantic_model", "planning", "app"):
        if type(features.get(key)) is not bool:
            raise DemoError(f"features.{key} must be true or false")
    if features["planning"] and not features["semantic_model"]:
        raise DemoError("Planning requires features.semantic_model=true")
    deployment = value.get("deployment")
    _keys(deployment, ["workspace_name", "lakehouse_name", "schema"], "deployment")
    _text(deployment.get("workspace_name"), "deployment.workspace_name", 120)
    _text(deployment.get("lakehouse_name"), "deployment.lakehouse_name", 100)
    schema = deployment.get("schema")
    if not isinstance(schema, str) or not re.fullmatch(r"demo_[a-z][a-z0-9_]{0,40}", schema):
        raise DemoError("deployment.schema must match demo_[a-z][a-z0-9_]{0,40}")
    research = value.get("research", {})
    _keys(research, ["industry_confirmed", "notes", "references"], "research")
    if type(research.get("industry_confirmed", False)) is not bool:
        raise DemoError("research.industry_confirmed must be true or false")
    if "notes" in research and not isinstance(research["notes"], str):
        raise DemoError("research.notes must be text")
    refs = research.get("references", [])
    if not isinstance(refs, list) or any(
        not isinstance(ref, str) or not ref.startswith("https://") for ref in refs
    ):
        raise DemoError("research.references must be a list of HTTPS source URLs")
    return value


def validate(value):
    _keys(value, ["version", "customer", "audience", "scenario", "sources", "scope",
                  "features", "deployment", "research", "proposal"], "configuration")
    if type(value.get("version")) is not int or value["version"] not in (1, 2):
        raise DemoError("version must be 1 or 2")
    scope = value.get("scope")
    if value["version"] == 2:
        return validate_brief(value)
    if "proposal" in value:
        raise DemoError("Legacy scenario configurations do not support proposal; use version 2")
    if not isinstance(value.get("scenario"), str) or value["scenario"] not in SCENARIOS:
        raise DemoError(f"scenario must be one of: {', '.join(SCENARIOS)}")
    _keys(scope, ["events", "regions", "locations", "months", "seed", "end_date"], "scope")
    validate_common(value)
    for key, lower, upper in [
        ("events", 100, 10000), ("regions", 3, 12), ("locations", 6, 24),
    ]:
        n = scope.get(key)
        if type(n) is not int or not lower <= n <= upper:
            raise DemoError(f"scope.{key} must be an integer from {lower} to {upper}")
    if scope["locations"] < scope["regions"]:
        raise DemoError("scope.locations must be at least scope.regions")
    return value


def validate_brief(value):
    """A brief can precede a proposed industry and schema."""
    _keys(value, ["version", "customer", "audience", "sources", "scope", "features",
                  "deployment", "research", "proposal"], "configuration")
    if type(value.get("version")) is not int or value["version"] != 2:
        raise DemoError("version must be 2")
    scope = value.get("scope")
    _keys(scope, ["months", "seed", "end_date", "max_rows_per_table", "max_total_rows"], "scope")
    validate_common(value)
    for key, lower, upper in [
        ("max_rows_per_table", 1, 100000), ("max_total_rows", 1, 1000000),
    ]:
        n = scope.get(key)
        if type(n) is not int or not lower <= n <= upper:
            raise DemoError(f"scope.{key} must be an integer from {lower} to {upper}")
    if value.get("proposal") is not None:
        from .blueprint import validate_proposal
        validate_proposal(value)
    return value


def brief():
    legacy = example()
    return {
        "version": 2, "customer": legacy["customer"], "audience": legacy["audience"],
        "sources": ["Describe the existing systems and the kinds of data they hold"],
        "scope": {"months": 12, "seed": 42, "end_date": "2026-09-30",
                  "max_rows_per_table": 10000, "max_total_rows": 100000},
        "features": legacy["features"], "deployment": legacy["deployment"],
        "research": legacy["research"], "proposal": None,
    }


def require_proposal(config):
    if config["version"] == 2 and config.get("proposal") is None:
        raise DemoError("Research the customer and propose a use case and synthetic schema first. "
                        "Run plan for the Copilot research brief; a website alone does not choose a schema.")


def load(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DemoError(f"Cannot read configuration {path}: {exc}") from exc
    return validate(value)


def example(scenario="healthcare-access"):
    return {
        "version": 1,
        "customer": {"name": "Example customer", "website": "https://example.com"},
        "audience": "Operations executives and data platform leaders",
        "scenario": scenario,
        "sources": ["Operational system: events, outcomes, sites and resources",
                    "ERP: financial exceptions by region and month",
                    "Risk system: regional assessments"],
        "scope": {"events": 1200, "regions": 6, "locations": 12,
                  "months": 12, "seed": 42, "end_date": "2026-09-30"},
        "features": {"semantic_model": False, "planning": False, "app": True},
        "deployment": {"workspace_name": "CHOOSE_AN_APPROVED_WORKSPACE",
                       "lakehouse_name": "lh_demo", "schema": "demo_customer"},
        "research": {"industry_confirmed": False, "notes": "", "references": []},
    }
