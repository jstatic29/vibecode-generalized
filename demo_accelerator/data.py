"""Portable deterministic generator, also embedded in the Fabric notebook."""

import calendar
import hashlib
from datetime import date, timedelta


def build_data(config):
    """Use integer money, explicit grains and independent contextual populations."""
    scope = config["scope"]
    seed = scope["seed"]

    def number(key, salt, modulus):
        value = f"{seed}:{key}:{salt}".encode("utf-8")
        return int.from_bytes(hashlib.sha256(value).digest()[:8], "big") % modulus

    end = date.fromisoformat(scope["end_date"])
    end_index = end.year * 12 + end.month - 1
    periods = []
    for index in range(end_index - scope["months"] + 1, end_index + 1):
        year, month = divmod(index, 12)
        periods.append(date(year, month + 1, 1).isoformat())
    regions = [{"region_id": i, "region_name": f"Illustrative Region {i:02d}"}
               for i in range(1, scope["regions"] + 1)]
    locations = [{"location_id": i, "location_name": f"Illustrative Site {i:02d}",
                  "region_id": (i - 1) % scope["regions"] + 1}
                 for i in range(1, scope["locations"] + 1)]
    resources = [{"resource_id": i + 1, "resource_name": name}
                 for i, name in enumerate(config["scenario_resources"])]
    reasons = [
        {"reason_id": 0, "reason_name": "No exception", "capacity_driven": False, "actionable": False},
        {"reason_id": 1, "reason_name": "Capacity unavailable", "capacity_driven": True, "actionable": True},
        {"reason_id": 2, "reason_name": "Required staff unavailable", "capacity_driven": True, "actionable": True},
        {"reason_id": 3, "reason_name": "External constraint", "capacity_driven": False, "actionable": False},
        {"reason_id": 4, "reason_name": "Service not suitable", "capacity_driven": False, "actionable": False},
    ]
    events = []
    for i in range(1, scope["events"] + 1):
        location = locations[number(i, "location", len(locations))]
        period = date.fromisoformat(periods[number(i, "month", len(periods))])
        days = calendar.monthrange(period.year, period.month)[1]
        if period.year == end.year and period.month == end.month:
            days = end.day
        when = period.replace(day=number(i, "day", days) + 1)
        # A visible but explicitly synthetic regional capacity pattern.
        has_exception = number(i, "exception", 100) < 15 + location["region_id"] * 4
        reason = 1 + number(i, "reason", 4) if has_exception else 0
        events.append({
            "event_id": i, "event_date": when.isoformat(),
            "location_id": location["location_id"], "region_id": location["region_id"],
            "resource_id": number(i, "resource", len(resources)) + 1,
            "reason_id": reason, "exception": has_exception,
            "time_critical": number(i, "critical", 100) < 18,
            "source_system": config["sources"][0],
        })
    # Bronze contains one duplicate and one invalid record to demonstrate actual cleaning.
    bronze_events = [dict(row) for row in events]
    bronze_events.append(dict(events[0]))
    invalid = dict(events[0], event_id=scope["events"] + 1, location_id=-1)
    bronze_events.append(invalid)
    finance = []
    risk = []
    for region in regions:
        rid = region["region_id"]
        for month in periods:
            finance.append({
                "finance_id": len(finance) + 1, "region_id": rid, "service_month": month,
                "amount_cents": 100000 + number(f"{rid}:{month}", "money", 900000),
                "source_system": config["sources"][min(1, len(config["sources"]) - 1)],
            })
        screened = 150 + number(rid, "screened", 200)
        risk.append({
            "risk_id": rid, "region_id": rid, "assessed": screened,
            "high_risk": 10 + number(rid, "risk", min(screened - 10, 100)),
            "source_system": config["sources"][-1],
        })
    valid_locations = {row["location_id"] for row in locations}
    seen = set()
    silver = []
    rejected = []
    duplicates = 0
    for row in bronze_events:
        if row["location_id"] not in valid_locations:
            rejected.append(row)
        elif row["event_id"] in seen:
            duplicates += 1
        else:
            seen.add(row["event_id"])
            silver.append(dict(row))
    start = date.fromisoformat(periods[0])
    dates = [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]
    date_rows = [{"date": d, "year": int(d[:4]), "month": int(d[5:7]),
                  "quarter": f"{d[:4]}-Q{(int(d[5:7]) - 1) // 3 + 1}"} for d in dates]
    tables = {
        "bronze_events": bronze_events, "bronze_finance": finance, "bronze_risk": risk,
        "silver_events": silver, "silver_finance": finance, "silver_risk": risk,
        "silver_rejected_events": rejected,
        "dim_region": regions, "dim_location": locations, "dim_resource": resources,
        "dim_reason": reasons, "dim_date": date_rows,
        "fact_event": silver, "fact_finance": finance, "fact_risk": risk,
    }
    capacity_reasons = {r["reason_id"] for r in reasons if r["capacity_driven"] and r["actionable"]}
    latest = max(row["quarter"] for row in date_rows)
    quarter_dates = {row["date"] for row in date_rows if row["quarter"] == latest}
    actionable = [r for r in silver if r["reason_id"] in capacity_reasons]
    rank = [{"region": region["region_name"], "actionable_events": sum(
        row["region_id"] == region["region_id"] and row["event_date"] in quarter_dates
        for row in actionable
    )} for region in regions]
    rank.sort(key=lambda row: (-row["actionable_events"], row["region"]))
    expected = {
        "events": len(silver), "bronze_events": len(bronze_events),
        "duplicates_removed": duplicates, "rejected_events": len(rejected),
        "actionable_events": len(actionable),
        "finance_cents": sum(row["amount_cents"] for row in finance),
        "assessed": sum(row["assessed"] for row in risk),
        "high_risk": sum(row["high_risk"] for row in risk),
        "latest_quarter": latest, "latest_quarter_is_complete": (
            end.month % 3 == 0 and end.day == calendar.monthrange(end.year, end.month)[1]
        ),
        "latest_quarter_events": sum(row["event_date"] in quarter_dates for row in silver),
        "latest_quarter_actionable": sum(row["event_date"] in quarter_dates for row in actionable),
        "latest_quarter_finance_cents": sum(
            row["amount_cents"] for row in finance if row["service_month"] in quarter_dates
        ),
        "latest_quarter_rank": rank,
    }
    return tables, expected
