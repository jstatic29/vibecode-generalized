"""Local, operator-supplied usage accounting; never a billing-system adapter."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext

from .config import DemoError


def template():
    return {
        "version": 1,
        "window": {"start": None, "end": None},
        "coverage_notes": "Record missing sessions, delayed metrics and excluded charges here.",
        "copilot": [{
            "scope_ref": "presenter-session-1",
            "attribution": "session",
            "credits": None,
            "evidence_ref": None,
            "captured_at": None,
            "rate": None,
        }],
        "fabric": [{
            "scope_ref": "pilot-items-capacity-operations",
            "billing_mode": "capacity",
            "cu_seconds": None,
            "evidence_ref": None,
            "captured_at": None,
            "rate": None,
        }],
    }


def _fields(value, required, label):
    if not isinstance(value, dict) or set(value) != set(required):
        raise DemoError(f"{label}: expected exactly these fields: {', '.join(required)}")


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise DemoError(f"{label}: a nonempty string is required")
    return value


def _time(value, label):
    try:
        result = datetime.fromisoformat(_text(value, label).replace("Z", "+00:00"))
    except ValueError as exc:
        raise DemoError(f"{label}: expected an ISO timestamp") from exc
    if result.utcoffset() is None:
        raise DemoError(f"{label}: timezone is required")
    return result


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise DemoError(f"{label}: expected a finite nonnegative number")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise DemoError(f"{label}: expected a finite nonnegative number") from exc
    if not number.is_finite() or number < 0:
        raise DemoError(f"{label}: expected a finite nonnegative number")
    if len(number.as_tuple().digits) > 28 or abs(number.as_tuple().exponent) > 28:
        raise DemoError(f"{label}: at most 28 digits and decimal places are supported")
    return number


def _rate(value, fabric):
    if value is None:
        return None
    fields = ["per_unit", "currency", "source", "as_of"]
    if fabric:
        fields.append("region")
    _fields(value, fields, "rate")
    amount = _number(value["per_unit"], "rate.per_unit")
    if not isinstance(value["currency"], str) or not re.fullmatch(r"[A-Z]{3}", value["currency"]):
        raise DemoError("rate.currency: expected a three-letter uppercase currency code")
    _text(value["source"], "rate.source")
    try:
        date.fromisoformat(_text(value["as_of"], "rate.as_of"))
    except ValueError as exc:
        raise DemoError("rate.as_of: expected an ISO date") from exc
    if fabric:
        _text(value["region"], "rate.region")
    return amount, value["currency"]


def _summarize(rows, fabric, start):
    if not isinstance(rows, list):
        raise DemoError("Usage entries must be an array")
    unit = "cu_seconds" if fabric else "credits"
    mode_field = "billing_mode" if fabric else "attribution"
    modes = ("capacity", "spark-autoscale", "nonbillable") if fabric else (
        "session", "isolated-account-delta", "shared-account-delta")
    seen = set()
    totals = dict.fromkeys(modes, Decimal(0))
    measured = 0
    approximate = False
    missing = []
    unpriced = []
    estimates = {}
    for row in rows:
        _fields(row, ["scope_ref", mode_field, unit, "evidence_ref", "captured_at", "rate"],
                "usage entry")
        scope = _text(row["scope_ref"], "scope_ref")
        if scope in seen:
            raise DemoError(f"Duplicate scope_ref: {scope}; remove overlapping measurements")
        seen.add(scope)
        mode = row[mode_field]
        if not isinstance(mode, str) or mode not in modes:
            raise DemoError(f"{mode_field}: expected one of {', '.join(modes)}")
        rate = _rate(row["rate"], fabric)
        if fabric and mode == "nonbillable" and rate is not None:
            raise DemoError("Nonbillable operations must not have a rate")
        if row[unit] is None:
            missing.append(scope)
            continue
        amount = _number(row[unit], unit)
        _text(row["evidence_ref"], "evidence_ref")
        if _time(row["captured_at"], "captured_at") < start:
            raise DemoError("captured_at must not precede the pilot window")
        measured += 1
        approximate = approximate or mode == "shared-account-delta"
        totals[mode] += amount
        if fabric and mode == "nonbillable":
            continue
        if rate is None:
            unpriced.append(scope)
        else:
            per_unit, currency = rate
            quantity = amount / 3600 if fabric else amount
            estimates[currency] = estimates.get(currency, Decimal(0)) + quantity * per_unit
    result = {
        "status": "incomplete" if missing or not rows else "reported",
        "measured_entries": measured,
        "missing_usage": missing,
        "unpriced_entries": unpriced,
        "estimated_cost_by_currency": (
            {currency: str(amount) for currency, amount in sorted(estimates.items())}
            if rows and not missing and not unpriced else None),
    }
    if fabric:
        result["cu_seconds_by_billing_mode"] = (
            {mode: str(amount) for mode, amount in totals.items()} if measured else None)
        result["cu_hours_by_billing_mode"] = (
            {mode: str(amount / 3600) for mode, amount in totals.items()} if measured else None)
    else:
        result["reported_credits"] = str(sum(totals.values())) if measured else None
        result["credits_by_attribution"] = (
            {mode: str(amount) for mode, amount in totals.items()} if measured else None)
        result["approximate"] = approximate
    return result


def summarize(data):
    _fields(data, ["version", "window", "coverage_notes", "copilot", "fabric"], "usage")
    if type(data["version"]) is not int or data["version"] != 1:
        raise DemoError("Unsupported pilot usage version")
    _fields(data["window"], ["start", "end"], "window")
    start = _time(data["window"]["start"], "window.start")
    end = _time(data["window"]["end"], "window.end")
    if end <= start:
        raise DemoError("window.end must be after window.start")
    _text(data["coverage_notes"], "coverage_notes")
    with localcontext() as context:
        context.prec = 80
        copilot = _summarize(data["copilot"], False, start)
        fabric = _summarize(data["fabric"], True, start)
    return {
        "version": 1,
        "window": data["window"],
        "coverage_notes": data["coverage_notes"],
        "provenance": "operator-supplied measurements and rates; not independently verified",
        "measurements": {"copilot": data["copilot"], "fabric": data["fabric"]},
        "copilot": copilot,
        "fabric": fabric,
        "limitations": [
            "Reported coverage only; missing entries are not zero and completeness is not verified.",
            "Do not overlap account deltas with session totals or Fabric exports with their detail rows.",
            "Credits, tokens, premium requests and internal model billing multipliers are different units.",
            "Capacity consumption valued at a CU-hour rate is an allocation estimate, not an invoice.",
            "Spark autoscale is separate from base capacity; do not count the same operation twice.",
            "Included Copilot credits need not incur incremental charges.",
            "Excludes licenses, storage, networking, other services and post-window activity.",
        ],
    }
