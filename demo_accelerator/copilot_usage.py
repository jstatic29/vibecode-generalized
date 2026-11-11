"""Read native Copilot usage without resuming a session or making model calls."""

import json
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

from .config import DemoError
from .pilot_usage import _number


def _object(value, label):
    if not isinstance(value, dict):
        raise DemoError(f"{label}: expected an object; unsupported Copilot usage format")
    return value


def _status(value):
    if value not in ("complete", "partial", "unavailable"):
        raise DemoError("Missing or unsupported aiCreditsStatus; cannot establish credit coverage")
    return value


def _nano(value):
    amount = _number(value, "totalNanoAiu")
    if amount != amount.to_integral_value():
        raise DemoError("totalNanoAiu must be an integer number of nano-AI units")
    return int(amount)


def _checkpoint(data):
    snapshot = _object(data.get("accountingSnapshot"), "accountingSnapshot")
    status = _status(snapshot.get("aiCreditsStatus"))
    total = snapshot.get("totalNanoAiu")
    if status != "unavailable" and total is None:
        raise DemoError("Credit total missing from native accounting snapshot")
    watermarks = _object(data.get("usageAccountingWatermarks"), "usageAccountingWatermarks")
    for source, sequence in watermarks.items():
        if not isinstance(source, str) or type(sequence) is not int or sequence < 0:
            raise DemoError("Unsupported usage accounting watermark")
    return _nano(total) if total is not None else None, status, dict(watermarks)


def read_session(session_dir):
    """Replay the latest checkpoint and newer deduplicated native credit records."""
    events = Path(session_dir) / "events.jsonl"
    total = None
    status = None
    watermarks = {}
    timestamp = None
    trailing = []
    with events.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                event = _object(json.loads(line, parse_float=str), f"event line {line_number}")
            except json.JSONDecodeError as exc:
                raise DemoError(
                    f"Incomplete/invalid session event at line {line_number}; retry after the turn ends"
                ) from exc
            kind = event.get("type")
            if kind == "session.usage_checkpoint":
                total, status, watermarks = _checkpoint(_object(event.get("data"), "checkpoint"))
                timestamp = event.get("timestamp")
                trailing = []
            elif kind == "session.usage_record":
                trailing.append(event)
    if status is None:
        raise DemoError("No supported native usage checkpoint; use /usage or a native usage export")
    for event in trailing:
        data = _object(event.get("data"), "usage record")
        usage = _object(data.get("usage"), "usage")
        accounting = _object(usage.get("accounting"), "usage.accounting")
        source = accounting.get("sourceSessionId")
        sequence = accounting.get("sequence")
        if not isinstance(source, str) or not source or type(sequence) is not int or sequence < 1:
            raise DemoError("Usage record lacks a supported source/sequence; cannot deduplicate")
        if sequence <= watermarks.get(source, 0):
            continue
        # A gap could omit billable work; do not treat a subtotal as complete.
        if sequence != watermarks.get(source, 0) + 1:
            raise DemoError("Gap in native usage records; wait for a fresh checkpoint or use /usage")
        watermarks[source] = sequence
        record_status = _status(usage.get("aiCreditsStatus"))
        copilot_usage = usage.get("copilotUsage")
        amount = (_object(copilot_usage, "copilotUsage").get("totalNanoAiu")
                  if copilot_usage is not None else None)
        if record_status != "unavailable" and amount is None:
            raise DemoError("Credit-bearing usage record is missing totalNanoAiu")
        if amount is not None:
            total = (total if total is not None else 0) + _nano(amount)
        if status != "complete" or record_status != "complete":
            status = "partial" if total is not None else "unavailable"
        timestamp = event.get("timestamp")
    return _capture(total, status, str(events), Path(session_dir).name, timestamp,
                    "native session checkpoint plus newer usage records")


def read_export(path, session_ref):
    """Read the CLI --usage-output-file / SDK usage.getMetrics result."""
    data = _object(json.loads(Path(path).read_text(encoding="utf-8-sig"),
                              parse_float=str), "usage export")
    status = _status(data.get("aiCreditsStatus"))
    total = data.get("totalNanoAiu")
    if total is None and status != "unavailable":
        raise DemoError("Usage export has no totalNanoAiu; premium requests are not AI credits")
    return _capture(_nano(total) if total is not None else None, status, str(path),
                    session_ref, None, "native CLI/SDK usage export")


def _capture(total, status, source, session_ref, timestamp, method):
    captured_at = datetime.now(timezone.utc).isoformat()
    with localcontext() as context:
        context.prec = 80
        credits = (format(Decimal(total).scaleb(-9), "f")
                   if total is not None and status != "unavailable" else None)
    return {
        "version": 1,
        "session_ref": session_ref,
        "captured_at": captured_at,
        "last_accounted_at": timestamp,
        "method": method,
        "source": source,
        "ai_credits_status": status,
        "total_nano_aiu": total,
        "reported_ai_credits": credits,
        "worksheet_entry": {
            "scope_ref": session_ref,
            "attribution": "session",
            "credits": credits if status == "complete" else None,
            "evidence_ref": source,
            "captured_at": captured_at,
            "rate": None,
        },
        "limitations": [
            "Snapshot of already recorded usage; in-flight work and this reply can add credits.",
            "Cumulative session total, not just the current turn or a reused session's pilot portion.",
            "Includes subagent usage only where the runtime attributes it to this session.",
            "Partial/unavailable totals must not be presented as complete pilot consumption.",
            "Native session-state format is runtime-specific; unsupported formats fail explicitly.",
            "AI credits are not currency or premium requests.",
        ],
    }
