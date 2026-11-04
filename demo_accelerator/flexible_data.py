"""Portable declarative data execution shared by local previews and Fabric notebooks."""

import hashlib
from datetime import date, timedelta


def build_blueprint(config):
    """Execute only validated recipes, with no eval, SQL or Python supplied by the proposal."""
    proposal = config["proposal"]
    scope = config["scope"]
    end = date.fromisoformat(scope["end_date"])
    index = end.year * 12 + end.month - scope["months"]
    start = date(index // 12, index % 12 + 1, 1)
    span = (end - start).days + 1
    definitions = {table["name"]: table for table in proposal["tables"]}
    pending = dict(definitions)
    tables = {}
    schemas = {}

    def number(table, row, column, modulus):
        key = f"{scope['seed']}:{table}:{row}:{column}".encode("utf-8")
        return int.from_bytes(hashlib.sha256(key).digest()[:8], "big") % modulus

    def matches(row, filters):
        for item in filters:
            left, right, op = row[item["column"]], item["value"], item["op"]
            if op == "eq":
                good = left == right
            elif op == "ne":
                good = left != right
            elif op == "gt":
                good = left > right
            elif op == "ge":
                good = left >= right
            elif op == "lt":
                good = left < right
            elif op == "le":
                good = left <= right
            elif op == "in":
                good = left in right
            else:
                raise ValueError(f"Unknown filter operator: {op}")
            if not good:
                return False
        return True

    while pending:
        ready = []
        for name, table in pending.items():
            deps = {table["from"]} if table.get("from") else set()
            deps.update(c["generator"]["table"] for c in table.get("columns", [])
                        if c["generator"]["kind"] == "reference")
            if deps <= tables.keys():
                ready.append(name)
        if not ready:
            raise ValueError("Unresolved schema dependencies")
        for name in sorted(ready):
            table = pending.pop(name)
            if "from" in table:
                schemas[name] = schemas[table["from"]]
                rows = [dict(row) for row in tables[table["from"]]
                        if matches(row, table.get("filters", []))]
                keys = table.get("deduplicate_by", [])
                if keys:
                    seen = set()
                    unique = []
                    for row in sorted(rows, key=lambda r: tuple(r[c] for c in schemas[name])):
                        key = tuple(row[c] for c in keys)
                        if key not in seen:
                            seen.add(key)
                            unique.append(row)
                    rows = unique
            else:
                schemas[name] = {c["name"]: c for c in table["columns"]}
                rows = []
                reference_values = {}
                for column in table["columns"]:
                    gen = column["generator"]
                    if gen["kind"] == "reference":
                        values = [r[gen["column"]] for r in tables[gen["table"]]]
                        if not values:
                            raise ValueError(f"{name}.{column['name']}: referenced table is empty")
                        reference_values[column["name"]] = values
                for i in range(table["rows"]):
                    row = {}
                    for column in table["columns"]:
                        cname, gen = column["name"], column["generator"]
                        kind = gen["kind"]
                        if kind == "sequence":
                            value = i + gen.get("start", 1)
                        elif kind == "integer":
                            value = gen["min"] + number(name, i, cname, gen["max"] - gen["min"] + 1)
                        elif kind == "choice":
                            value = gen["values"][number(name, i, cname, len(gen["values"]))]
                        elif kind == "boolean":
                            value = number(name, i, cname, 100) < gen["true_percent"]
                        elif kind == "date":
                            value = (start + timedelta(days=number(name, i, cname, span))).isoformat()
                        elif kind == "label":
                            value = f"{gen['prefix']} {i + 1:03d}"
                        elif kind == "reference":
                            values = reference_values[cname]
                            value = values[number(name, i, cname, len(values))]
                        else:
                            raise ValueError(f"Unknown generator: {kind}")
                        row[cname] = value
                    rows.append(row)
            key = table.get("key")
            if key and len({r[key] for r in rows}) != len(rows):
                raise ValueError(f"{name}.{key}: proposed unique key is not unique")
            tables[name] = rows

    checks = []
    for name, columns in schemas.items():
        for cname, column in columns.items():
            gen = column["generator"]
            if gen["kind"] == "reference":
                valid = {row[gen["column"]] for row in tables[gen["table"]]}
                missing = sum(row[cname] not in valid for row in tables[name])
                if missing:
                    raise ValueError(f"{name}.{cname}: {missing} invalid references")
                checks.append({"table": name, "column": cname, "target": gen["table"],
                               "target_key": gen["column"], "missing": missing})
    metrics = {}
    for metric in proposal["metrics"]:
        rows = [r for r in tables[metric["table"]] if matches(r, metric.get("filters", []))]
        column, agg = metric.get("column"), metric["aggregation"]

        def aggregate(values):
            if agg == "count":
                return len(values)
            if not values:
                return None
            total = sum(row[column] for row in values)
            return total / len(values) if agg == "avg" else total

        grouped = {}
        group_by = metric.get("group_by", [])
        if group_by:
            for row in rows:
                key = tuple(row[c] for c in group_by)
                grouped.setdefault(key, []).append(row)
        groups = [dict(zip(group_by, key), **{metric["name"]: aggregate(values)})
                  for key, values in sorted(grouped.items())]
        latest = None
        if metric.get("time_column"):
            quarter = (end.month - 1) // 3 + 1
            selected = [r for r in rows
                        if r[metric["time_column"]][:4] == str(end.year)
                        and (int(r[metric["time_column"]][5:7]) - 1) // 3 + 1 == quarter]
            quarter_start = date(end.year, (quarter - 1) * 3 + 1, 1)
            next_quarter = date(end.year + 1, 1, 1) if quarter == 4 else date(end.year, quarter * 3 + 1, 1)
            latest = {"period": f"{end.year}-Q{quarter}", "value": aggregate(selected),
                      "complete": start <= quarter_start and end == next_quarter - timedelta(days=1)}
        metrics[metric["name"]] = {
            "value": aggregate(rows), "groups": groups, "unit": metric["unit"],
            "latest_quarter": latest,
        }
    counts = {name: len(rows) for name, rows in tables.items()}
    raw_counts = {t["name"]: counts[t["name"]] for t in proposal["tables"] if t["layer"] == "bronze"}
    expected = {
        "table_counts": counts,
        "delta_table_count": len(tables) + 2,
        "raw_extract_count": len(raw_counts),
        "physical_rows": sum(counts.values()) + sum(raw_counts.values()) + 2 * len(tables) + 3,
        "date_window": {"start": start.isoformat(), "end": end.isoformat()},
        "metrics": metrics,
        "referential_integrity": checks,
    }
    if expected["physical_rows"] > scope["max_total_rows"]:
        raise ValueError("Generated rows exceed the approved physical-work budget")
    return tables, expected
