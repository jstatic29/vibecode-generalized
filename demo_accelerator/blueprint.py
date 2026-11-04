"""Industry-independent, declarative synthetic schemas; never execute proposal code."""

import re
from datetime import date

from .config import DemoError, _keys, _text


IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")
TYPES = {"string": str, "int64": int, "boolean": bool, "date": str}
LAYERS = {"bronze", "silver", "gold", "supporting"}
OPERATORS = {"eq", "ne", "gt", "ge", "lt", "le", "in"}
SAFE_INTEGER = 2**53 - 1


def column_reference(proposal, table, column):
    """Resolve business lineage, including copied keys from a dependent source."""
    spec = column_map(proposal)[table][column]
    if "references" in spec:
        return spec["references"]
    gen = spec["generator"]
    if gen["kind"] == "reference":
        return {"table": gen["table"], "column": gen["column"]}
    if gen["kind"] == "lookup":
        return column_reference(proposal, gen["table"], gen["column"])
    return None


def identifier(value, label):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise DemoError(f"{label} must be a lowercase SQL identifier (letters, digits, underscores)")
    return value


def literal(value, kind):
    if kind == "date":
        if not isinstance(value, str):
            return False
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return False
        return parsed.isoformat() == value
    return type(value) is TYPES[kind]


def ordered_tables(proposal):
    """Topological order covers transformations and synthetic FK dependencies."""
    definitions = {table["name"]: table for table in proposal["tables"]}
    pending = dict(definitions)
    ordered = []
    done = set()
    while pending:
        ready = []
        for name, table in pending.items():
            deps = {table["from"]} if table.get("from") else set()
            deps.update(column["generator"]["table"] for column in table.get("columns", [])
                        if column["generator"].get("kind") in {"reference", "lookup", "allocate"})
            deps.update(column["references"]["table"] for column in table.get("columns", [])
                        if "references" in column)
            missing = deps - definitions.keys()
            if missing:
                raise DemoError(f"{name}: unknown table dependencies {sorted(missing)}")
            if deps <= done:
                ready.append(name)
        if not ready:
            raise DemoError(f"Cyclic table dependencies: {', '.join(pending)}")
        for name in sorted(ready):
            ordered.append(pending.pop(name))
            done.add(name)
    return ordered


def column_map(proposal):
    result = {}
    for table in ordered_tables(proposal):
        if "from" in table:
            source = result[table["from"]]
            result[table["name"]] = {name: dict(column) for name, column in source.items()}
        else:
            result[table["name"]] = {column["name"]: column for column in table["columns"]}
    return result


def validate_filters(filters, columns, label):
    if not isinstance(filters, list):
        raise DemoError(f"{label}.filters must be a list")
    for item in filters:
        _keys(item, ["column", "op", "value"], f"{label} filter")
        column, op, value = item.get("column"), item.get("op"), item.get("value")
        if (not isinstance(column, str) or column not in columns
                or not isinstance(op, str) or op not in OPERATORS):
            raise DemoError(f"{label}: filter needs a known column and supported operator")
        kind = columns[column]["type"]
        values = value if op == "in" else [value]
        if not isinstance(values, list) or not values or not all(literal(v, kind) for v in values):
            raise DemoError(f"{label}: filter values must match {column}'s {kind} type")


def validate_proposal(config):
    proposal = config["proposal"]
    _keys(proposal, ["industry", "title", "business_question", "audience_rationale", "decision",
                     "assumptions", "tables", "metrics", "derived_metrics", "reporting"], "proposal")
    for field in ("industry", "title", "business_question", "audience_rationale", "decision"):
        _text(proposal.get(field), f"proposal.{field}", 2000)
    assumptions = proposal.get("assumptions")
    if not isinstance(assumptions, list) or not assumptions:
        raise DemoError("proposal.assumptions must disclose synthetic and inferred assumptions")
    for item in assumptions:
        _text(item, "proposal assumption", 2000)
    tables = proposal.get("tables")
    if not isinstance(tables, list) or not tables:
        raise DemoError("proposal.tables must describe the proposed schema")
    names = set()
    row_bounds = {}
    for table in tables:
        _keys(table, ["name", "layer", "grain", "purpose", "source", "rows", "columns",
                      "key", "from", "deduplicate_by", "filters", "unique_by"], "table")
        name = identifier(table.get("name"), "table.name")
        if name.startswith("meta_"):
            raise DemoError(f"{name}: meta_ is reserved for generated governance tables")
        if name in names:
            raise DemoError(f"Duplicate table name: {name}")
        names.add(name)
        if not isinstance(table.get("layer"), str) or table["layer"] not in LAYERS:
            raise DemoError(f"{name}: layer must be bronze, silver, gold or supporting")
        for field in ("grain", "purpose"):
            _text(table.get(field), f"{name}.{field}", 1000)
        if "key" in table:
            identifier(table["key"], f"{name}.key")
        if "from" in table:
            identifier(table["from"], f"{name}.from")
            if any(field in table for field in ("columns", "rows", "source")):
                raise DemoError(f"{name}: transformed tables inherit columns, row bound and source")
        else:
            if any(field in table for field in ("deduplicate_by", "filters")):
                raise DemoError(f"{name}: cleaning operations require a from table")
            n = table.get("rows")
            if type(n) is not int or not 1 <= n <= config["scope"]["max_rows_per_table"]:
                raise DemoError(f"{name}: rows must fit scope.max_rows_per_table")
            source = table.get("source")
            if type(source) is not int or not 0 <= source < len(config["sources"]):
                raise DemoError(f"{name}: source must be an index into the supplied source descriptions")
            columns = table.get("columns")
            if not isinstance(columns, list) or not columns:
                raise DemoError(f"{name}: columns must be a nonempty list")
            seen = set()
            for column in columns:
                _keys(column, ["name", "type", "description", "generator", "references"], f"{name} column")
                cname = identifier(column.get("name"), f"{name}.column")
                if cname in seen:
                    raise DemoError(f"{name}: duplicate column {cname}")
                seen.add(cname)
                kind = column.get("type")
                if not isinstance(kind, str) or kind not in TYPES:
                    raise DemoError(f"{name}.{cname}: supported types are {', '.join(TYPES)}")
                _text(column.get("description"), f"{name}.{cname}.description", 1000)
                if "references" in column:
                    _keys(column["references"], ["table", "column"], f"{name}.{cname}.references")
                    for field in ("table", "column"):
                        identifier(column["references"].get(field), f"{name}.{cname}.references.{field}")
                gen = column.get("generator")
                if not isinstance(gen, dict):
                    raise DemoError(f"{name}.{cname}: generator must be an object")
                recipe = gen.get("kind")
                label = f"{name}.{cname}"
                allowed = {
                    "sequence": ["kind", "start"],
                    "integer": ["kind", "min", "max"],
                    "choice": ["kind", "values", "mode"],
                    "boolean": ["kind", "true_percent"],
                    "date": ["kind"],
                    "label": ["kind", "prefix"],
                    "reference": ["kind", "table", "column", "mode", "stride"],
                    "date_sequence": ["kind", "frequency"],
                    "date_part": ["kind", "column", "part"],
                    "date_offset": ["kind", "column", "min_days", "max_days"],
                    "lookup": ["kind", "table", "column", "via", "min_days", "max_days"],
                    "map": ["kind", "column", "cases"],
                    "scaled_integer": ["kind", "column", "factor_column", "divisor"],
                    "difference": ["kind", "left", "right"],
                    "allocate": ["kind", "table", "via", "total_column", "factor_column", "divisor"],
                }
                if not isinstance(recipe, str) or recipe not in allowed:
                    raise DemoError(f"{label}: unsupported generator {recipe!r}; extend/test the engine, "
                                    "do not insert executable code into proposals")
                _keys(gen, allowed[recipe], label)
                if recipe == "sequence":
                    if kind != "int64" or type(gen.get("start", 1)) is not int:
                        raise DemoError(f"{label}: sequence requires int64 and an integer start")
                elif recipe == "integer":
                    if (kind != "int64" or type(gen.get("min")) is not int
                            or type(gen.get("max")) is not int or gen["max"] < gen["min"]):
                        raise DemoError(f"{label}: integer needs int64 and min <= max")
                elif recipe == "choice":
                    values = gen.get("values")
                    if not isinstance(values, list) or not values or not all(literal(v, kind) for v in values):
                        raise DemoError(f"{label}: choice values must match {kind}")
                    if kind == "int64" and any(abs(v) > 2**53 - 1 for v in values):
                        raise DemoError(f"{label}: integer choices exceed the exact numeric range")
                    if gen.get("mode", "random") not in ("random", "cycle"):
                        raise DemoError(f"{label}: choice mode must be random or cycle")
                elif recipe == "boolean":
                    percent = gen.get("true_percent")
                    if kind != "boolean" or type(percent) is not int or not 0 <= percent <= 100:
                        raise DemoError(f"{label}: boolean needs true_percent from 0 to 100")
                elif recipe == "date":
                    if kind != "date":
                        raise DemoError(f"{label}: date generator requires date type")
                elif recipe == "label":
                    if kind != "string":
                        raise DemoError(f"{label}: label generator requires string type")
                    _text(gen.get("prefix"), f"{label}.prefix", 200)
                elif recipe in ("reference", "lookup", "allocate"):
                    identifier(gen.get("table"), f"{label}.table")
                    if recipe != "allocate":
                        identifier(gen.get("column"), f"{label}.column")
                    if recipe == "reference":
                        if gen.get("mode", "random") not in ("random", "cycle"):
                            raise DemoError(f"{label}: reference mode must be random or cycle")
                        if type(gen.get("stride", 1)) is not int or not 1 <= gen.get("stride", 1) <= 1000000:
                            raise DemoError(f"{label}: reference stride must be a positive bounded integer")
                        if "stride" in gen and gen.get("mode") != "cycle":
                            raise DemoError(f"{label}: stride requires cycle mode")
                    else:
                        identifier(gen.get("via"), f"{label}.via")
                elif recipe == "date_sequence":
                    if kind != "date" or gen.get("frequency") not in ("day", "month"):
                        raise DemoError(f"{label}: date_sequence needs date and day/month frequency")
                    end = date.fromisoformat(config["scope"]["end_date"])
                    index = end.year * 12 + end.month - config["scope"]["months"]
                    start = date(index // 12, index % 12 + 1, 1)
                    count = (end - start).days + 1 if gen["frequency"] == "day" else config["scope"]["months"]
                    if n != count:
                        raise DemoError(f"{label}: date_sequence rows must equal its complete window ({count})")
                elif recipe in ("date_part", "date_offset", "map", "scaled_integer"):
                    identifier(gen.get("column"), f"{label}.column")
                elif recipe == "difference":
                    identifier(gen.get("left"), f"{label}.left")
                    identifier(gen.get("right"), f"{label}.right")
                if recipe in ("scaled_integer", "allocate"):
                    if kind != "int64" or type(gen.get("divisor")) is not int or not 1 <= gen["divisor"] <= SAFE_INTEGER:
                        raise DemoError(f"{label}: scaled amounts need int64 and a positive safe divisor")
                    identifier(gen.get("factor_column"), f"{label}.factor_column")
                    if recipe == "allocate":
                        identifier(gen.get("total_column"), f"{label}.total_column")
                if kind == "int64" and recipe in ("integer", "sequence"):
                    candidates = (gen.get("start", 1), gen.get("start", 1) + n,
                                  gen.get("min", 0), gen.get("max", 0))
                    if any(abs(v) > 2**53 - 1 for v in candidates):
                        raise DemoError(f"{label}: integers must fit exact JavaScript-safe money/key range")
    columns = column_map(proposal)
    by_name = {table["name"]: table for table in tables}
    bounds = {}
    for table in ordered_tables(proposal):
        name = table["name"]
        row_bounds[name] = row_bounds[table["from"]] if "from" in table else table["rows"]
        key = table.get("key")
        if key and key not in columns[name]:
            raise DemoError(f"{name}: key column does not exist")
        if table["layer"] == "gold" and not key:
            raise DemoError(f"{name}: gold tables need an explicit unique key for ontology binding")
        if "from" in table:
            dedup = table.get("deduplicate_by", [])
            if not isinstance(dedup, list) or any(not isinstance(c, str) or c not in columns[name] for c in dedup):
                raise DemoError(f"{name}: deduplicate_by needs known columns")
            validate_filters(table.get("filters", []), columns[name], name)
        unique = table.get("unique_by", [])
        if (not isinstance(unique, list) or any(not isinstance(c, str) or c not in columns[name] for c in unique)
                or len(set(unique)) != len(unique)):
            raise DemoError(f"{name}: unique_by needs distinct known columns")
        previous = {}
        for cname, column in columns[name].items():
            gen = column["generator"]
            recipe, kind = gen["kind"], column["type"]
            label = f"{name}.{cname}"
            if "from" in table:
                bounds[name, cname] = bounds[table["from"], cname]
                continue
            def local(field, required_type=None):
                c = gen.get(field)
                if not isinstance(c, str) or c not in previous or (
                    required_type and previous[c]["type"] != required_type
                ):
                    raise DemoError(f"{label}: {field} must name an earlier {required_type or 'typed'} column")
                return c

            bound = None
            if gen["kind"] == "reference":
                target = gen["table"]
                target_column = columns[target].get(gen["column"])
                if (not target_column or target_column["type"] != column["type"]
                        or by_name[target].get("key") != gen["column"]):
                    raise DemoError(f"{name}.{cname}: reference must target a same-typed declared unique key")
                bound = bounds[target, gen["column"]]
            elif recipe in ("lookup", "allocate"):
                via = local("via")
                ref = previous[via]["generator"]
                if ref["kind"] != "reference" or ref["table"] != gen["table"]:
                    raise DemoError(f"{label}: via must directly reference the specified parent table")
                target_cols = columns[gen["table"]]
                if recipe == "lookup":
                    if gen["column"] not in target_cols or target_cols[gen["column"]]["type"] != kind:
                        raise DemoError(f"{label}: lookup must copy a same-typed parent column")
                    bound = bounds[gen["table"], gen["column"]]
                    if "min_days" in gen or "max_days" in gen:
                        if (kind != "date" or type(gen.get("min_days")) is not int
                                or type(gen.get("max_days")) is not int
                                or not 0 <= gen["min_days"] <= gen["max_days"] <= 365):
                            raise DemoError(f"{label}: lookup date offset needs 0 <= min_days <= max_days <= 365")
                else:
                    if ref.get("mode") != "cycle" or ref.get("stride", 1) != 1:
                        raise DemoError(f"{label}: allocation requires a stride-1 cycle reference")
                    if table["rows"] < row_bounds[gen["table"]]:
                        raise DemoError(f"{label}: allocation must provide at least one child per parent")
                    for field in ("total_column", "factor_column"):
                        if gen[field] not in target_cols or target_cols[gen[field]]["type"] != "int64":
                            raise DemoError(f"{label}: allocation inputs must be parent int64 columns")
                    total = bounds[gen["table"], gen["total_column"]]
                    factor = bounds[gen["table"], gen["factor_column"]]
                    if total[0] < 0 or factor[0] < 0 or total[1] * factor[1] > SAFE_INTEGER:
                        raise DemoError(f"{label}: allocation needs nonnegative safe intermediate amounts")
                    bound = (0, total[1] * factor[1] // gen["divisor"])
            elif recipe in ("integer", "sequence", "choice"):
                if recipe == "integer":
                    bound = (gen["min"], gen["max"])
                elif recipe == "sequence":
                    bound = (gen.get("start", 1), gen.get("start", 1) + table["rows"] - 1)
                elif kind == "int64":
                    bound = (min(gen["values"]), max(gen["values"]))
            elif recipe == "map":
                source = local("column")
                cases = gen.get("cases")
                if not isinstance(cases, list) or not cases:
                    raise DemoError(f"{label}: map requires explicit cases, with no silent default")
                seen_cases = []
                for case in cases:
                    _keys(case, ["when", "value"], label)
                    if (not literal(case.get("when"), previous[source]["type"])
                            or not literal(case.get("value"), kind) or case["when"] in seen_cases):
                        raise DemoError(f"{label}: map cases must be distinct and type matched")
                    seen_cases.append(case["when"])
                if kind == "int64":
                    bound = (min(c["value"] for c in cases), max(c["value"] for c in cases))
            elif recipe == "difference":
                left, right = local("left", "int64"), local("right", "int64")
                if kind != "int64":
                    raise DemoError(f"{label}: difference output must be int64")
                a, b = bounds[name, left], bounds[name, right]
                bound = (a[0] - b[1], a[1] - b[0])
            elif recipe == "scaled_integer":
                value, factor = local("column", "int64"), local("factor_column", "int64")
                products = [a * b for a in bounds[name, value] for b in bounds[name, factor]]
                if any(abs(v) > SAFE_INTEGER for v in products):
                    raise DemoError(f"{label}: scaled intermediate exceeds exact numeric range")
                bound = (min(products) // gen["divisor"], max(products) // gen["divisor"])
            elif recipe == "date_part":
                local("column", "date")
                part = gen.get("part")
                if part not in ("year", "quarter", "month", "month_start") or kind != (
                    "date" if part == "month_start" else "int64"
                ):
                    raise DemoError(f"{label}: date_part needs year/quarter/month int64 or month_start date")
                if kind == "int64":
                    bound = (1, 9999 if part == "year" else 12 if part == "month" else 4)
            elif recipe == "date_offset":
                local("column", "date")
                if (kind != "date" or type(gen.get("min_days")) is not int
                        or type(gen.get("max_days")) is not int
                        or not 0 <= gen["min_days"] <= gen["max_days"] <= 365):
                    raise DemoError(f"{label}: date_offset needs date and 0 <= min_days <= max_days <= 365")
            if bound and any(abs(v) > SAFE_INTEGER for v in bound):
                raise DemoError(f"{label}: computed integers exceed exact numeric range")
            bounds[name, cname] = bound
            previous[cname] = column
    for table in tables:
        for cname, column in columns[table["name"]].items():
            ref = column_reference(proposal, table["name"], cname)
            if ref and (by_name[ref["table"]].get("key") != ref["column"]
                        or ref["column"] not in columns[ref["table"]]
                        or columns[ref["table"]][ref["column"]]["type"] != column["type"]):
                raise DemoError(f"{table['name']}.{cname}: declared relationship must target a same-typed unique key")
    metrics = proposal.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise DemoError("proposal.metrics must define at least one measurable demo outcome")
    metric_names = set()
    view_names = set()

    def numeric_bound(table, column):
        return max(abs(v) for v in bounds[table, column])

    for metric in metrics:
        _keys(metric, ["name", "label", "table", "aggregation", "column", "filters", "group_by",
                       "time_column", "unit", "interpretation", "period_grain"], "metric")
        name = identifier(metric.get("name"), "metric.name")
        if name in metric_names:
            raise DemoError(f"Duplicate metric {name}")
        metric_names.add(name)
        for field in ("label", "unit", "interpretation"):
            _text(metric.get(field), f"{name}.{field}", 1000)
        table_name = metric.get("table")
        if not isinstance(table_name, str) or table_name not in by_name or by_name[table_name]["layer"] != "gold":
            raise DemoError(f"{name}: metric must use an existing gold table")
        cols = columns[table_name]
        agg = metric.get("aggregation")
        if not isinstance(agg, str) or agg not in {"count", "sum", "avg"}:
            raise DemoError(f"{name}: aggregation must be count, sum or avg")
        if agg != "count" and (
            not isinstance(metric.get("column"), str) or metric["column"] not in cols
            or cols[metric["column"]]["type"] != "int64"
        ):
            raise DemoError(f"{name}: sum/avg needs an int64 column")
        if agg == "count" and "column" in metric:
            raise DemoError(f"{name}: count counts rows; omit column")
        if agg != "count" and numeric_bound(table_name, metric["column"]) * row_bounds[table_name] > 2**53 - 1:
            raise DemoError(f"{name}: aggregate upper bound exceeds exact numeric range; use smaller amounts/volumes")
        group = metric.get("group_by", [])
        if (not isinstance(group, list) or any(not isinstance(c, str) or c not in cols for c in group)
                or len(set(group)) != len(group) or name in group):
            raise DemoError(f"{name}: group_by needs distinct known columns different from metric name")
        time_column = metric.get("time_column")
        if time_column is not None and (
            not isinstance(time_column, str) or time_column not in cols or cols[time_column]["type"] != "date"
        ):
            raise DemoError(f"{name}: time_column must be a date column")
        if metric.get("period_grain", "quarter") not in ("quarter", "month") or (
            "period_grain" in metric and not time_column
        ):
            raise DemoError(f"{name}: period_grain requires a date and month/quarter")
        if time_column and (set(group) | {name}) & {"demo_year", "demo_quarter", "demo_month"}:
            raise DemoError(f"{name}: period view aliases demo_year/demo_quarter are reserved")
        views = {f"vw_{name}", f"vw_{name}_period"} if time_column else {f"vw_{name}"}
        if views & (view_names | names):
            raise DemoError(f"{name}: generated aggregate view name collision")
        view_names.update(views)
        validate_filters(metric.get("filters", []), cols, name)
    derived = proposal.get("derived_metrics", [])
    if not isinstance(derived, list):
        raise DemoError("proposal.derived_metrics must be a list")
    metric_defs = {m["name"]: m for m in metrics}
    metric_bounds = {m["name"]: row_bounds[m["table"]] * (
        numeric_bound(m["table"], m["column"]) if m["aggregation"] != "count" else 1) for m in metrics}
    for metric in derived:
        _keys(metric, ["name", "label", "operation", "left", "right", "unit", "interpretation"], "derived metric")
        name = identifier(metric.get("name"), "derived metric.name")
        for field in ("label", "unit", "interpretation"):
            _text(metric.get(field), f"{name}.{field}", 1000)
        left, right = metric.get("left"), metric.get("right")
        if (not isinstance(left, str) or left not in metric_defs
                or not isinstance(right, str) or right not in metric_defs):
            raise DemoError(f"{name}: operands must name earlier metrics")
        a, b = metric_defs[left], metric_defs[right]
        if a["aggregation"] != "sum" or b["aggregation"] != "sum":
            raise DemoError(f"{name}: operands must be additive sums or differences, not counts/averages/ratios")
        if (a.get("group_by", []) != b.get("group_by", [])
                or bool(a.get("time_column")) != bool(b.get("time_column"))
                or a.get("period_grain", "quarter") != b.get("period_grain", "quarter")):
            raise DemoError(f"{name}: operands must have identical grouping and period grains")
        for key in a.get("group_by", []) + (["time_column"] if a.get("time_column") else []):
            ca = a.get(key) if key == "time_column" else key
            cb = b.get(key) if key == "time_column" else key
            ra, rb = column_reference(proposal, a["table"], ca), column_reference(proposal, b["table"], cb)
            if not ra or ra != rb:
                raise DemoError(f"{name}: operands need conformed dimension keys and date lineage")
        operation = metric.get("operation")
        if operation not in ("difference", "ratio"):
            raise DemoError(f"{name}: derived operation must be difference or ratio")
        if a["unit"] != b["unit"]:
            raise DemoError(f"{name}: operands must use the same units")
        if operation == "difference" and metric["unit"] != a["unit"]:
            raise DemoError(f"{name}: difference must preserve its operand units")
        if operation == "ratio" and metric["unit"] != "ratio":
            raise DemoError(f"{name}: ratio unit must be ratio (0.10 represents 10%)")
        views = {f"vw_{name}", f"vw_{name}_period"} if a.get("time_column") else {f"vw_{name}"}
        if name in metric_defs or views & (view_names | names):
            raise DemoError(f"{name}: duplicate metric or generated view name collision")
        if set(a.get("group_by", [])) & {name} or name in {"demo_year", "demo_quarter", "demo_month"}:
            raise DemoError(f"{name}: derived name conflicts with group or period aliases")
        view_names.update(views)
        bound = metric_bounds[left] + metric_bounds[right]
        if operation == "difference" and bound > SAFE_INTEGER:
            raise DemoError(f"{name}: aggregate upper bound exceeds exact numeric range")
        metric_bounds[name] = bound
        metric_defs[name] = dict(a, name=name, unit=metric["unit"],
                                 aggregation="sum" if operation == "difference" else "ratio")
    if "reporting" in proposal:
        reporting = proposal["reporting"]
        _keys(reporting, ["calendar_table", "calendar_column", "period_table", "period_column",
                          "as_of_date", "notes"], "reporting")
        for prefix in ("calendar", "period"):
            t, c = reporting.get(f"{prefix}_table"), reporting.get(f"{prefix}_column")
            if (not isinstance(t, str) or t not in by_name or not isinstance(c, str)
                    or by_name[t]["layer"] != "gold" or by_name[t].get("key") != c
                    or columns[t][c]["type"] != "date"):
                raise DemoError(f"reporting.{prefix}: needs a gold date key")
        if not literal(reporting.get("as_of_date"), "date"):
            raise DemoError("reporting.as_of_date must be an ISO date")
        _text(reporting.get("notes"), "reporting.notes", 4000)
    if not any(t["layer"] == "bronze" for t in tables) or not any(t["layer"] == "silver" for t in tables):
        raise DemoError("Proposal must demonstrate bronze and silver alongside its gold metric tables")
    # Budget actual physical work, including raw JSON and governance, not a table-count quota.
    raw_bound = sum(row_bounds[t["name"]] for t in tables if t["layer"] == "bronze")
    total_bound = sum(row_bounds.values()) + raw_bound + 2 * len(tables) + 3
    if total_bound > config["scope"]["max_total_rows"]:
        raise DemoError(f"Proposed workload upper bound {total_bound} exceeds scope.max_total_rows "
                        f"({config['scope']['max_total_rows']}); reduce rows or approve a larger budget")
    return config


def relationships(proposal):
    """Expose only gold-to-gold key references; keep staging out of the ontology."""
    tables = {t["name"]: t for t in proposal["tables"]}
    cols = column_map(proposal)
    result = []
    for table in proposal["tables"]:
        if table["layer"] != "gold":
            continue
        for name, col in cols[table["name"]].items():
            ref = column_reference(proposal, table["name"], name)
            if ref and tables[ref["table"]]["layer"] == "gold":
                result.append({"name": f"{table['name']}_{name}", "source": table["name"],
                               "source_fk": name, "target": ref["table"], "target_key": ref["column"]})
    return result
