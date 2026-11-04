"""Compile every customer-facing surface from the proposed schema and metrics."""

import inspect
import json

from . import flexible_data
from .blueprint import column_map, ordered_tables, relationships
from .config import digest


def scenario_contract(config):
    proposal = config["proposal"]
    return {
        "customer": config["customer"], "audience": config["audience"],
        "sources": config["sources"], "synthetic": True,
        "industry": proposal["industry"], "title": proposal["title"],
        "question": proposal["business_question"], "decision": proposal["decision"],
        "audience_rationale": proposal["audience_rationale"],
        "assumptions": proposal["assumptions"],
        "tables": proposal["tables"], "metrics": proposal["metrics"],
        "derived_metrics": proposal.get("derived_metrics", []),
        "reporting": proposal.get("reporting"),
        "scope": config["scope"], "features": config["features"],
        "deployment": config["deployment"], "research": config.get("research", {}),
    }


def ontology_contract(config):
    proposal = config["proposal"]
    cols = column_map(proposal)
    return {
        "schema": config["deployment"]["schema"], "generation": 2,
        "entities": [
            {"name": t["name"], "table": t["name"], "key": t["key"], "grain": t["grain"],
             "description": t["purpose"],
             "properties": [{"name": c, "column": c, "type": spec["type"],
                             "description": spec["description"]} for c, spec in cols[t["name"]].items()]}
            for t in proposal["tables"] if t["layer"] == "gold"
        ],
        "relationships": relationships(proposal),
        "rules": proposal["assumptions"],
        "metrics": proposal["metrics"], "derived_metrics": proposal.get("derived_metrics", []),
        "reporting": proposal.get("reporting"),
        "authoring_notes": [
            "Authoring contract, NOT a Fabric item definition. Use current generation-2 TMDL APIs.",
            "Use the declared names consistently; no geography, capacity, risk or finance entities are implied.",
            "Persist lineage tags and diff portal-written bindings; verify actual graph keys/properties/edges.",
            "Validate each metric's table grain and filters against expected.json.",
            "All numeric fields use int64; money uses explicitly documented minor units, not Decimal.",
        ],
    }


def sql_literal(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    return "'" + value.replace("'", "''") + "'"


def where(filters):
    operators = {"eq": "=", "ne": "<>", "gt": ">", "ge": ">=", "lt": "<", "le": "<="}
    parts = []
    for item in filters:
        col = f"[{item['column']}]"
        if item["op"] == "in":
            parts.append(f"{col} IN ({', '.join(sql_literal(v) for v in item['value'])})")
        else:
            parts.append(f"{col} {operators[item['op']]} {sql_literal(item['value'])}")
    return "\nWHERE " + " AND ".join(parts) if parts else ""


def metric_views(config):
    result = []
    schema = config["deployment"]["schema"]
    for metric in config["proposal"]["metrics"]:
        agg = metric["aggregation"]
        expression = "COUNT_BIG(*)" if agg == "count" else (
            f"SUM([{metric['column']}])" if agg == "sum" else f"AVG(CAST([{metric['column']}] AS float))"
        )
        for period in (False, True) if metric.get("time_column") else (False,):
            names = list(metric.get("group_by", []))
            groups = [f"[{c}]" for c in names]
            selected = list(groups)
            if period:
                # Use distinct alias names to avoid collisions with customer columns.
                year = f"YEAR([{metric['time_column']}])"
                quarter = f"DATEPART(quarter,[{metric['time_column']}])"
                selected.extend([f"{year} AS [demo_year]", f"{quarter} AS [demo_quarter]"])
                groups.extend([year, quarter])
                if metric.get("period_grain") == "month":
                    month = f"MONTH([{metric['time_column']}])"
                    selected.append(f"{month} AS [demo_month]")
                    groups.append(month)
            selected.append(f"{expression} AS [{metric['name']}]")
            view = f"vw_{metric['name']}" + ("_period" if period else "")
            query = (
                f"CREATE OR ALTER VIEW [{schema}].[{view}] AS\nSELECT {', '.join(selected)}\n"
                f"FROM [{schema}].[{metric['table']}]"
                + where(metric.get("filters", []))
                + ("\nGROUP BY " + ", ".join(groups) if groups else "") + ";\n"
            )
            result.append({"name": view, "metric": metric["name"], "period": period, "sql": query})
    definitions = {m["name"]: m for m in config["proposal"]["metrics"]}
    for metric in config["proposal"].get("derived_metrics", []):
        definition = definitions[metric["left"]]
        for period in (False, True) if definition.get("time_column") else (False,):
            keys = list(definition.get("group_by", []))
            if period:
                keys += ["demo_year", "demo_quarter"]
                if definition.get("period_grain") == "month":
                    keys.append("demo_month")
            suffix = "_period" if period else ""
            left = f"a.[{metric['left']}]"
            right = f"b.[{metric['right']}]"
            expression = f"{left} - {right}" if metric["operation"] == "difference" else (
                f"CAST({left} AS float) / NULLIF({right}, 0)")
            selected = [f"COALESCE(a.[{k}], b.[{k}]) AS [{k}]" for k in keys]
            selected.append(f"{expression} AS [{metric['name']}]")
            join = "FULL OUTER JOIN" if keys else "CROSS JOIN"
            condition = "\nON " + " AND ".join(f"a.[{k}] = b.[{k}]" for k in keys) if keys else ""
            view = f"vw_{metric['name']}{suffix}"
            query = (
                f"CREATE OR ALTER VIEW [{schema}].[{view}] AS\nSELECT {', '.join(selected)}\n"
                f"FROM [{schema}].[vw_{metric['left']}{suffix}] a\n"
                f"{join} [{schema}].[vw_{metric['right']}{suffix}] b{condition};\n"
            )
            result.append({"name": view, "metric": metric["name"], "period": period, "sql": query})
        definitions[metric["name"]] = definition
    return result


def analytical_sql(config):
    return "-- Synthetic aggregates; no fact-to-fact joins. Execute each GO-separated batch separately.\n" + (
        "\nGO\n".join(view["sql"] for view in metric_views(config))
    )


def semantic_contract(config):
    proposal = config["proposal"]
    measures = {}
    for metric in proposal["metrics"]:
        table = metric["table"]
        agg = metric["aggregation"]
        expression = f"COALESCE(COUNTROWS('{table}'), 0)" if agg == "count" else (
            f"{'SUM' if agg == 'sum' else 'AVERAGE'}('{table}'[{metric['column']}])"
        )
        filters = []
        ops = {"eq": "=", "ne": "<>", "gt": ">", "ge": ">=", "lt": "<", "le": "<="}
        for item in metric.get("filters", []):
            def dax_literal(value):
                if isinstance(value, bool):
                    return "TRUE()" if value else "FALSE()"
                if isinstance(value, int):
                    return str(value)
                if column_map(proposal)[table][item["column"]]["type"] == "date":
                    y, m, d = map(int, value.split("-"))
                    return f"DATE({y},{m},{d})"
                return '"' + value.replace('"', '""') + '"'
            field = f"'{table}'[{item['column']}]"
            if item["op"] == "in":
                filters.append(f"{field} IN {{{', '.join(dax_literal(v) for v in item['value'])}}}")
            else:
                filters.append(f"{field} {ops[item['op']]} {dax_literal(item['value'])}")
        if filters:
            expression = f"CALCULATE({expression}, {', '.join(f'KEEPFILTERS({f})' for f in filters)})"
        measures[metric["name"]] = {"label": metric["label"], "expression": expression,
                                    "unit": metric["unit"], "interpretation": metric["interpretation"],
                                    "format_string": "#,0.00" if agg == "avg" else "#,0"}
    for metric in proposal.get("derived_metrics", []):
        left, right = f"[{metric['left']}]", f"[{metric['right']}]"
        expression = (
            f"IF(ISBLANK({left}) || ISBLANK({right}), BLANK(), {left} - {right})"
            if metric["operation"] == "difference" else f"DIVIDE({left}, {right})"
        )
        measures[metric["name"]] = {
            "label": metric["label"], "expression": expression, "unit": metric["unit"],
            "interpretation": metric["interpretation"],
            "format_string": "0.0%;-0.0%;0.0%" if metric["unit"] == "ratio" else "#,0",
        }
    return {
        "enabled": config["features"]["semantic_model"], "planning": config["features"]["planning"],
        "preferred_mode": "DirectLake", "fallback": "Import requires approval after compatibility check",
        "tables": [t["name"] for t in proposal["tables"] if t["layer"] == "gold"],
        "relationships": relationships(proposal), "measures": measures,
        "reporting": proposal.get("reporting"),
        "notes": [
            "Contract only. Inspect actual schema and author through supported semantic-model tooling.",
            "Review relationship directions and ambiguous paths before authoring; infer no extra joins.",
            "Use single-direction dimension-to-fact filtering; do not activate fact-to-fact paths.",
            "Derived measures compare independently aggregated facts; missing operands stay blank, not zero.",
            "For dated facts, add/verify a contiguous date dimension and date key when authoring the model; "
            "if this needs new physical tables, revise the proposal and obtain fresh design approval.",
            "Reconcile every metric including filters and periods against expected.json.",
            "Units are those declared in the metric, not automatically dollars or percentages.",
            "Keep identity stable after Plan binding; stop on credential errors; verify second-viewer access.",
        ],
        "planning_steps": [
            "Verify feature availability and storage-mode compatibility; never assume Direct Lake works.",
            "Confirm planable measures/grains and a dedicated approved SQL writeback destination.",
            "Guide portal Plan binding, destination and write permissions where no API is available.",
            "Let Planning create destination tables; save an illustrative scenario and verify readback.",
        ],
    }


def notebook(config):
    setup = (
        "import json\nimport hashlib\nfrom datetime import date, timedelta\n"
        "from pyspark.sql import functions as F, types as T, Window\n"
        f"config = json.loads({json.dumps(json.dumps(config))})\n"
        f"SCHEMA = {config['deployment']['schema']!r}\n"
        f"CONFIG_HASH = {digest(config)!r}\n"
        + inspect.getsource(flexible_data.build_blueprint)
        + "\ntables, expected = build_blueprint(config)\n"
    )
    schemas = column_map(config["proposal"])
    definitions = ordered_tables(config["proposal"])
    setup += (
        f"schemas = json.loads({json.dumps(json.dumps(schemas))})\n"
        f"definitions = json.loads({json.dumps(json.dumps(definitions))})\n"
    )
    execute = """
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{SCHEMA}`")
if spark.sql(f"SHOW TABLES IN `{SCHEMA}`").count():
    raise RuntimeError("Target schema is populated. Use a fresh approved demo schema.")

def frame(name, rows):
    types = {"string": T.StringType(), "int64": T.LongType(),
             "boolean": T.BooleanType(), "date": T.StringType()}
    schema = T.StructType([T.StructField(c, types[v["type"]], False)
                           for c, v in schemas[name].items()])
    result = spark.createDataFrame(rows, schema)
    for c, v in schemas[name].items():
        if v["type"] == "date":
            result = result.withColumn(c, F.to_date(F.col(c)))
    return result

def predicate(filters):
    result = F.lit(True)
    for item in filters:
        left, op = F.col(item["column"]), item["op"]
        right = F.col(item["other_column"]) if "other_column" in item else item["value"]
        if op == "eq": value = left == right
        elif op == "ne": value = left != right
        elif op == "gt": value = left > right
        elif op == "ge": value = left >= right
        elif op == "lt": value = left < right
        elif op == "le": value = left <= right
        elif op == "in": value = left.isin(right)
        else: raise ValueError(f"Unknown operator {op}")
        result = result & value
    return result

for definition in definitions:
    name = definition["name"]
    if "from" in definition:
        result = spark.table(f"{SCHEMA}.{definition['from']}").filter(
            predicate(definition.get("filters", [])))
        if definition.get("deduplicate_by"):
            window = Window.partitionBy(*definition["deduplicate_by"]).orderBy(*schemas[name])
            result = result.withColumn("__demo_row_number", F.row_number().over(window)).filter(
                F.col("__demo_row_number") == 1).drop("__demo_row_number")
    else:
        result = frame(name, tables[name])
    if definition["layer"] == "bronze":
        path = f"Files/demo_accelerator/{SCHEMA}/{CONFIG_HASH[:12]}/{name}"
        result.coalesce(1).write.mode("errorifexists").json(path)
        result = spark.read.schema(result.schema).json(path)
    result.write.format("delta").mode("errorifexists").saveAsTable(f"{SCHEMA}.{name}")

for definition in definitions:
    name = definition["name"]
    actual = spark.table(f"{SCHEMA}.{name}")
    assert actual.count() == expected["table_counts"][name], f"Row count mismatch: {name}"
    # Exact bidirectional row reconciliation also checks staging transformations.
    reference = frame(name, tables[name]).select(actual.columns)
    assert actual.exceptAll(reference).count() == 0, f"Unexpected rows: {name}"
    assert reference.exceptAll(actual).count() == 0, f"Missing rows: {name}"
    if definition.get("key"):
        assert actual.select(definition["key"]).distinct().count() == actual.count(), f"Duplicate key: {name}"
    if definition.get("unique_by"):
        assert actual.select(*definition["unique_by"]).distinct().count() == actual.count(), f"Duplicate grain: {name}"
    if definition.get("checks"):
        assert actual.filter(~predicate(definition["checks"])).count() == 0, f"Row checks failed: {name}"
for relation in expected["referential_integrity"]:
    missing = spark.table(f"{SCHEMA}.{relation['table']}").join(
        spark.table(f"{SCHEMA}.{relation['target']}").select(
            F.col(relation["target_key"]).alias(relation["column"])), relation["column"], "left_anti").count()
    assert missing == 0, f"Invalid references: {relation}"

def aggregate(frame, metric):
    agg = metric["aggregation"]
    if agg == "count": return frame.count()
    function = F.sum if agg == "sum" else F.avg
    return frame.agg(function(metric["column"])).first()[0]

verified_metrics = {}
for metric in config["proposal"]["metrics"]:
    actual = spark.table(f"{SCHEMA}.{metric['table']}").filter(predicate(metric.get("filters", [])))
    baseline = expected["metrics"][metric["name"]]
    assert aggregate(actual, metric) == baseline["value"], f"Metric mismatch: {metric['name']}"
    verified_metrics[metric["name"]] = {"value": aggregate(actual, metric), "latest_quarter": None}
    if metric.get("time_column"):
        end = date.fromisoformat(config["scope"]["end_date"])
        dated = actual.filter((F.year(metric["time_column"]) == end.year) &
                             (F.quarter(metric["time_column"]) == (end.month - 1) // 3 + 1))
        assert aggregate(dated, metric) == baseline["latest_quarter"]["value"], "Period metric mismatch"
        verified_metrics[metric["name"]]["latest_quarter"] = aggregate(dated, metric)
    group = metric.get("group_by", [])
    for period in (False, True) if metric.get("time_column") else (False,):
        framed = actual
        keys = list(group)
        if period:
            framed = framed.withColumn("demo_year", F.year(metric["time_column"])).withColumn(
                "demo_quarter", F.quarter(metric["time_column"]))
            keys += ["demo_year", "demo_quarter"]
            if metric.get("period_grain") == "month":
                framed = framed.withColumn("demo_month", F.month(metric["time_column"]))
                keys.append("demo_month")
        if keys:
            function = F.count(F.lit(1)) if metric["aggregation"] == "count" else (
                F.sum(metric["column"]) if metric["aggregation"] == "sum" else F.avg(metric["column"]))
            observed = [{k: v.isoformat() if isinstance(v, date) else v for k, v in r.asDict().items()}
                        for r in framed.groupBy(*keys).agg(function.alias(metric["name"])).collect()]
            wanted = baseline["periods" if period else "groups"]
            assert sorted(observed, key=repr) == sorted(wanted, key=repr), f"Grouped metric mismatch: {metric['name']}"

for metric in config["proposal"].get("derived_metrics", []):
    observed = {}
    for scope in ("value", "latest_quarter"):
        left = verified_metrics[metric["left"]][scope]
        right = verified_metrics[metric["right"]][scope]
        value = None if left is None or right is None else (
            left - right if metric["operation"] == "difference" else left / right if right else None)
        baseline = expected["metrics"][metric["name"]]
        target = baseline["value"] if scope == "value" else (
            baseline["latest_quarter"]["value"] if baseline["latest_quarter"] else None)
        assert value == target, f"Derived metric mismatch: {metric['name']}"
        observed[scope] = value
    verified_metrics[metric["name"]] = observed

lineage = [{"table_name": t["name"], "source": t.get("from", config["sources"][t.get("source", 0)]),
            "layer": t["layer"], "grain": t["grain"]} for t in definitions]
spark.createDataFrame(lineage).write.format("delta").mode("errorifexists").saveAsTable(f"{SCHEMA}.meta_lineage")
catalog = [{"table_name": name, "row_count": len(rows), "classification": "Synthetic demo only"}
           for name, rows in tables.items()]
catalog += [{"table_name": "meta_lineage", "row_count": len(tables), "classification": "Synthetic demo only"},
            {"table_name": "meta_dictionary", "row_count": len(tables) + 2, "classification": "Synthetic demo only"}]
spark.createDataFrame(catalog).write.format("delta").mode("errorifexists").saveAsTable(f"{SCHEMA}.meta_dictionary")
assert spark.table(f"{SCHEMA}.meta_dictionary").count() == expected["delta_table_count"], "Catalog incomplete"
print(json.dumps({"config_hash": CONFIG_HASH, "verified": True, "expected": expected}))
"""
    cells = [
        {"cell_type": "markdown", "metadata": {}, "source": [
            "# Approved customer-specific synthetic schema\n",
            "Durable notebook job only. No overwrite/reset. Table count comes from the proposal.\n",
        ]},
        *[{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
           "source": text.splitlines(keepends=True)} for text in (setup, execute)],
    ]
    for index, cell in enumerate(cells):
        cell["id"] = f"demo-cell-{index}"
    return {"nbformat": 4, "nbformat_minor": 5, "cells": cells,
            "metadata": {"kernelspec": {"display_name": "Synapse PySpark",
                                       "language": "python", "name": "synapse_pyspark"},
                         "language_info": {"name": "python"}}}


def generate(config, root, write_json, operator_guide):
    tables, expected = flexible_data.build_blueprint(config)
    proposal = config["proposal"]
    for filename, value in {
        "config.json": config, "scenario.json": scenario_contract(config),
        "ontology-contract.json": ontology_contract(config),
        "semantic-model-contract.json": semantic_contract(config),
        "expected.json": expected, "notebooks/build_demo.ipynb": notebook(config),
    }.items():
        write_json(root / filename, value)
    for name, rows in tables.items():
        write_json(root / "preview" / f"{name}.json", rows)
    (root / "aggregate-views.sql").write_text(analytical_sql(config), encoding="utf-8")
    (root / "data-agent-instructions.md").write_text(
        f"# {proposal['title']}\n\nQuestion: {proposal['business_question']}\n\n"
        "Use scenario.json and ontology-contract.json for the declared business meaning, grains, "
        "relationships and assumptions. Use proposal metrics exactly; no implied capacity, geography, "
        "financial or risk definitions. Query only the approved gold tables. Each metric has its own "
        "filters, units, grouping and optional time column; undated metrics must stay explicitly undated. "
        "Use aggregate-views.sql for independent aggregation; never multiply facts by joining raw facts. "
        "Return all metrics via SQL, not model arithmetic. Rank by metric then named group keys to break ties. "
        "Round once. Disclose synthetic data and incomplete periods. Keep tool requests below 1,000 characters.\n\n"
        f"Reporting context: {json.dumps(proposal.get('reporting', {}))}\n\n"
        f"Derived metrics: {json.dumps(proposal.get('derived_metrics', []))}\n\n"
        "Derived metrics join independently aggregated views on every declared group/period key. "
        "Reaggregate additive components before calculating ratios; never sum or average displayed ratios. "
        "Missing operands or zero denominators stay null. Invoice cohorts are not historical AP snapshots.\n\n"
        "Preserve publishing instructions: deliver agent output as-is without summarizing, rephrasing or "
        "adding interpretation. Test draft and published behavior separately; example validation can differ.\n",
        encoding="utf-8",
    )
    (root / "graph-query-patterns.gql").write_text(
        "// Topology check; author customer-specific walks from ontology-contract.json.\n"
        "MATCH ()-[e]->()\nRETURN labels(e) AS relationship, count(*) AS edges\nGROUP BY relationship\n"
        "// No healthcare-specific walk is substituted for the approved schema.\n", encoding="utf-8",
    )
    write_json(root / "app-contract.json", {
        "enabled": config["features"]["app"],
        "title": proposal["title"], "decision": proposal["decision"],
        "story": [proposal["business_question"], proposal["audience_rationale"],
                  "Ask a grounded question", proposal["decision"]],
        "aggregate_views": [{k: v for k, v in item.items() if k != "sql"} for item in metric_views(config)],
        "metrics": proposal["metrics"],
        "derived_metrics": proposal.get("derived_metrics", []),
        "reporting": proposal.get("reporting"),
        "action_context": "Choose business keys/grain from the approved proposal; do not assume county/region",
        "permissions": "Authenticated read; service-enforced create/update/delete for claims.sub = owner_id",
        "safety": [
            "Aggregate-only analytics connector. Application authentication reads as owner; disclose this.",
            "Snapshot fallback requires approval and timestamp labelling.",
            "Action and Planning databases are separate; actions do not update ontology or agent.",
            "Verify built-bundle parseability and actual signed-in deployed connector/CRUD/ownership.",
        ],
    })
    (root / "OPERATOR.md").write_text(operator_guide(config), encoding="utf-8")
    return expected
