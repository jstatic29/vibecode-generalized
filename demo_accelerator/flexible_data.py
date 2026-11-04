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
            left = row[item["column"]]
            right = row[item["other_column"]] if "other_column" in item else item["value"]
            op = item["op"]
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
                        if c["generator"]["kind"] in {"reference", "lookup", "allocate"})
            deps.update(c["references"]["table"] for c in table.get("columns", []) if "references" in c)
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
                parent_rows = {}
                for column in table["columns"]:
                    gen = column["generator"]
                    if gen["kind"] == "reference":
                        values = [r[gen["column"]] for r in tables[gen["table"]]]
                        if not values:
                            raise ValueError(f"{name}.{column['name']}: referenced table is empty")
                        reference_values[column["name"]] = (
                            sorted(values) if gen.get("mode") == "cycle" else values)
                    if gen["kind"] in ("lookup", "allocate"):
                        via = schemas[name][gen["via"]]["generator"]
                        parent_rows[gen["via"]] = {r[via["column"]]: r for r in tables[gen["table"]]}
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
                            offset = i % len(gen["values"]) if gen.get("mode") == "cycle" else number(
                                name, i, cname, len(gen["values"]))
                            value = gen["values"][offset]
                        elif kind == "boolean":
                            value = number(name, i, cname, 100) < gen["true_percent"]
                        elif kind == "date":
                            value = (start + timedelta(days=number(name, i, cname, span))).isoformat()
                        elif kind == "label":
                            value = f"{gen['prefix']} {i + 1:03d}"
                        elif kind == "reference":
                            values = reference_values[cname]
                            offset = (i // gen.get("stride", 1)) % len(values) if gen.get("mode") == "cycle" else number(
                                name, i, cname, len(values))
                            value = values[offset]
                        elif kind == "date_sequence":
                            if gen["frequency"] == "day":
                                value = (start + timedelta(days=i)).isoformat()
                            else:
                                month = start.year * 12 + start.month - 1 + i
                                value = date(month // 12, month % 12 + 1, 1).isoformat()
                        elif kind == "date_part":
                            source = date.fromisoformat(row[gen["column"]])
                            value = {
                                "year": source.year, "month": source.month,
                                "quarter": (source.month - 1) // 3 + 1,
                                "month_start": source.replace(day=1).isoformat(),
                            }[gen["part"]]
                        elif kind == "date_offset":
                            source = date.fromisoformat(row[gen["column"]])
                            value = (source + timedelta(days=gen["min_days"] + number(
                                name, i, cname, gen["max_days"] - gen["min_days"] + 1))).isoformat()
                        elif kind == "lookup":
                            value = parent_rows[gen["via"]][row[gen["via"]]][gen["column"]]
                            if "min_days" in gen:
                                value = (date.fromisoformat(value) + timedelta(days=gen["min_days"] + number(
                                    name, i, cname, gen["max_days"] - gen["min_days"] + 1))).isoformat()
                        elif kind == "map":
                            cases = [c["value"] for c in gen["cases"] if c["when"] == row[gen["column"]]]
                            if len(cases) != 1:
                                raise ValueError(f"{name}.{cname}: no unique map case for {row[gen['column']]!r}")
                            value = cases[0]
                        elif kind == "difference":
                            value = row[gen["left"]] - row[gen["right"]]
                        elif kind == "scaled_integer":
                            value = row[gen["column"]] * row[gen["factor_column"]] // gen["divisor"]
                        elif kind == "allocate":
                            parent = parent_rows[gen["via"]][row[gen["via"]]]
                            total = parent[gen["total_column"]] * parent[gen["factor_column"]] // gen["divisor"]
                            count = len(parent_rows[gen["via"]])
                            position, ordinal = i % count, i // count
                            children = table["rows"] // count + int(position < table["rows"] % count)
                            value = total // children + int(ordinal < total % children)
                        else:
                            raise ValueError(f"Unknown generator: {kind}")
                        row[cname] = value
                    rows.append(row)
            key = table.get("key")
            if key and len({r[key] for r in rows}) != len(rows):
                raise ValueError(f"{name}.{key}: proposed unique key is not unique")
            unique = table.get("unique_by", [])
            if unique and len({tuple(r[c] for c in unique) for r in rows}) != len(rows):
                raise ValueError(f"{name}: proposed unique_by grain is not unique")
            if any(not matches(row, table.get("checks", [])) for row in rows):
                raise ValueError(f"{name}: declared row checks failed")
            for row in rows:
                for cname, spec in schemas[name].items():
                    if spec["type"] == "date":
                        date.fromisoformat(row[cname])
            tables[name] = rows

    def reference(table, column):
        spec = schemas[table][column]
        if "references" in spec:
            return spec["references"]
        gen = spec["generator"]
        if gen["kind"] == "reference":
            return {"table": gen["table"], "column": gen["column"]}
        if gen["kind"] == "lookup":
            return reference(gen["table"], gen["column"])
        return None

    checks = []
    for name, columns in schemas.items():
        for cname, column in columns.items():
            ref = reference(name, cname)
            if ref:
                valid = {row[ref["column"]] for row in tables[ref["table"]]}
                missing = sum(row[cname] not in valid for row in tables[name])
                if missing:
                    raise ValueError(f"{name}.{cname}: {missing} invalid references")
                checks.append({"table": name, "column": cname, "target": ref["table"],
                               "target_key": ref["column"], "missing": missing})
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
        periods = []
        quarters = []
        if metric.get("time_column"):
            quarter = (end.month - 1) // 3 + 1
            selected = [r for r in rows
                        if r[metric["time_column"]][:4] == str(end.year)
                        and (int(r[metric["time_column"]][5:7]) - 1) // 3 + 1 == quarter]
            quarter_start = date(end.year, (quarter - 1) * 3 + 1, 1)
            next_quarter = date(end.year + 1, 1, 1) if quarter == 4 else date(end.year, quarter * 3 + 1, 1)
            latest = {"period": f"{end.year}-Q{quarter}", "value": aggregate(selected),
                      "complete": start <= quarter_start and end == next_quarter - timedelta(days=1)}
            for frequency, destination in (("month", periods), ("quarter", quarters)):
                bucket = {}
                for row in rows:
                    d = date.fromisoformat(row[metric["time_column"]])
                    keys = (d.year, (d.month - 1) // 3 + 1) + ((d.month,) if frequency == "month" else ())
                    keys = tuple(row[c] for c in group_by) + keys
                    bucket.setdefault(keys, []).append(row)
                names = group_by + ["demo_year", "demo_quarter"] + (["demo_month"] if frequency == "month" else [])
                for keys, values in sorted(bucket.items()):
                    destination.append(dict(zip(names, keys), **{metric["name"]: aggregate(values)}))
            quarter_totals = []
            for year, q in sorted({(r["demo_year"], r["demo_quarter"]) for r in quarters}):
                selected = [r for r in rows if int(r[metric["time_column"]][:4]) == year
                            and (int(r[metric["time_column"]][5:7]) - 1) // 3 + 1 == q]
                qstart = date(year, (q - 1) * 3 + 1, 1)
                qend = date(year + 1, 1, 1) if q == 4 else date(year, q * 3 + 1, 1)
                quarter_totals.append({"period": f"{year}-Q{q}", "value": aggregate(selected),
                                       "complete": start <= qstart and end >= qend - timedelta(days=1)})
        metrics[metric["name"]] = {
            "value": aggregate(rows), "groups": groups, "unit": metric["unit"],
            "latest_quarter": latest,
            "periods": periods if metric.get("period_grain") == "month" else quarters,
            "quarters": quarter_totals if metric.get("time_column") else [],
        }
    metric_defs = {m["name"]: m for m in proposal["metrics"]}
    for metric in proposal.get("derived_metrics", []):
        left, right = metrics[metric["left"]], metrics[metric["right"]]
        definition = metric_defs[metric["left"]]

        def calculate(a, b):
            if a is None or b is None:
                return None
            return a - b if metric["operation"] == "difference" else a / b if b != 0 else None

        def combine(a, b, keys):
            l = {tuple(r[k] for k in keys): r for r in a}
            r = {tuple(row[k] for k in keys): row for row in b}
            return [dict(zip(keys, key), **{metric["name"]: calculate(
                l.get(key, {}).get(metric["left"]), r.get(key, {}).get(metric["right"]))})
                for key in sorted(l.keys() | r.keys())]

        group = definition.get("group_by", [])
        period_keys = ["demo_year", "demo_quarter"] + (
            ["demo_month"] if definition.get("period_grain") == "month" else [])
        latest = None
        if left["latest_quarter"]:
            latest = dict(left["latest_quarter"], value=calculate(
                left["latest_quarter"]["value"], right["latest_quarter"]["value"]))
        quarters = []
        lq, rq = {r["period"]: r for r in left["quarters"]}, {r["period"]: r for r in right["quarters"]}
        for period in sorted(lq.keys() | rq.keys()):
            a, b = lq.get(period, {}), rq.get(period, {})
            quarters.append({"period": period, "value": calculate(a.get("value"), b.get("value")),
                             "complete": bool(a.get("complete") and b.get("complete"))})
        metrics[metric["name"]] = {
            "value": calculate(left["value"], right["value"]), "unit": metric["unit"],
            "groups": combine(left["groups"], right["groups"], group),
            "periods": combine(left["periods"], right["periods"], group + period_keys),
            "latest_quarter": latest, "quarters": quarters,
        }
        metric_defs[metric["name"]] = definition
    counts = {name: len(rows) for name, rows in tables.items()}
    raw_counts = {t["name"]: counts[t["name"]] for t in proposal["tables"] if t["layer"] == "bronze"}
    expected = {
        "table_counts": counts,
        "delta_table_count": len(tables) + 2,
        "raw_extract_count": len(raw_counts),
        "physical_rows": sum(counts.values()) + sum(raw_counts.values()) + 2 * len(tables) + 2,
        "date_window": {"start": start.isoformat(), "end": end.isoformat()},
        "metrics": metrics,
        "referential_integrity": checks,
    }
    if expected["physical_rows"] > scope["max_total_rows"]:
        raise ValueError("Generated rows exceed the approved physical-work budget")
    return tables, expected
