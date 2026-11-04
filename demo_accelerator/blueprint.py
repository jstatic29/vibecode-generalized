"""Industry-independent, declarative synthetic schemas; never execute proposal code."""

import re
from datetime import date

from .config import DemoError, _keys, _text


IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")
TYPES = {"string": str, "int64": int, "boolean": bool, "date": str}
LAYERS = {"bronze", "silver", "gold", "supporting"}
OPERATORS = {"eq", "ne", "gt", "ge", "lt", "le", "in"}


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
                        if column["generator"].get("kind") == "reference")
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
                     "assumptions", "tables", "metrics"], "proposal")
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
                      "key", "from", "deduplicate_by", "filters"], "table")
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
                _keys(column, ["name", "type", "description", "generator"], f"{name} column")
                cname = identifier(column.get("name"), f"{name}.column")
                if cname in seen:
                    raise DemoError(f"{name}: duplicate column {cname}")
                seen.add(cname)
                kind = column.get("type")
                if not isinstance(kind, str) or kind not in TYPES:
                    raise DemoError(f"{name}.{cname}: supported types are {', '.join(TYPES)}")
                _text(column.get("description"), f"{name}.{cname}.description", 1000)
                gen = column.get("generator")
                if not isinstance(gen, dict):
                    raise DemoError(f"{name}.{cname}: generator must be an object")
                recipe = gen.get("kind")
                label = f"{name}.{cname}"
                allowed = {
                    "sequence": ["kind", "start"],
                    "integer": ["kind", "min", "max"],
                    "choice": ["kind", "values"],
                    "boolean": ["kind", "true_percent"],
                    "date": ["kind"],
                    "label": ["kind", "prefix"],
                    "reference": ["kind", "table", "column"],
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
                else:
                    identifier(gen.get("table"), f"{label}.table")
                    identifier(gen.get("column"), f"{label}.column")
                if kind == "int64":
                    candidates = (gen.get("start", 1), gen.get("start", 1) + n,
                                  gen.get("min", 0), gen.get("max", 0))
                    if any(abs(v) > 2**53 - 1 for v in candidates):
                        raise DemoError(f"{label}: integers must fit exact JavaScript-safe money/key range")
    columns = column_map(proposal)
    by_name = {table["name"]: table for table in tables}
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
        for cname, column in columns[name].items():
            gen = column["generator"]
            if gen["kind"] == "reference":
                target = gen["table"]
                target_column = columns[target].get(gen["column"])
                if (not target_column or target_column["type"] != column["type"]
                        or by_name[target].get("key") != gen["column"]):
                    raise DemoError(f"{name}.{cname}: reference must target a same-typed declared unique key")
    metrics = proposal.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise DemoError("proposal.metrics must define at least one measurable demo outcome")
    metric_names = set()
    view_names = set()

    def numeric_bound(table, column):
        gen = columns[table][column]["generator"]
        if gen["kind"] == "reference":
            return numeric_bound(gen["table"], gen["column"])
        if gen["kind"] == "integer":
            return max(abs(gen["min"]), abs(gen["max"]))
        if gen["kind"] == "sequence":
            return max(abs(gen.get("start", 1)), abs(gen.get("start", 1) + row_bounds[table] - 1))
        return max(abs(value) for value in gen["values"])

    for metric in metrics:
        _keys(metric, ["name", "label", "table", "aggregation", "column", "filters", "group_by",
                       "time_column", "unit", "interpretation"], "metric")
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
        if time_column and (set(group) | {name}) & {"demo_year", "demo_quarter"}:
            raise DemoError(f"{name}: period view aliases demo_year/demo_quarter are reserved")
        views = {f"vw_{name}", f"vw_{name}_period"} if time_column else {f"vw_{name}"}
        if views & (view_names | names):
            raise DemoError(f"{name}: generated aggregate view name collision")
        view_names.update(views)
        validate_filters(metric.get("filters", []), cols, name)
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
            gen = col["generator"]
            if gen["kind"] == "reference" and tables[gen["table"]]["layer"] == "gold":
                result.append({"name": f"{table['name']}_{name}", "source": table["name"],
                               "source_fk": name, "target": gen["table"], "target_key": gen["column"]})
    return result
