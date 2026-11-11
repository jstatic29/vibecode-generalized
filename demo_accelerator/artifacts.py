"""Compile a single scenario contract into reviewable deployment work packages."""

import inspect
import json
from pathlib import Path

from . import data
from .config import SCENARIOS, digest, existing_mode, require_proposal


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def scenario_contract(config):
    if config["version"] == 2:
        from .flexible_artifacts import scenario_contract as flexible
        require_proposal(config)
        return flexible(config)
    scenario = SCENARIOS[config["scenario"]]
    return {
        "customer": config["customer"],
        "audience": config["audience"],
        "scenario": config["scenario"],
        "industry": scenario["industry"],
        "question": scenario["question"],
        "event_name": scenario["event"],
        "metric": scenario["metric"],
        "context": scenario["context"],
        "finance": scenario["finance"],
        "sources": config["sources"],
        "synthetic": True,
        "assumptions": [
            "This is an illustrative scenario, not evidence of a customer's actual problem.",
            "Region and site labels are fictional; no real person or customer record is used.",
            "Risk and finance are independent populations linked at region grain, not event grain.",
            "Associations are not causal findings. Rules are illustrative, not customer-approved policy.",
            "Risk assessments are undated and must be described as all-time.",
            "The latest data quarter may be partial; never call it last complete quarter without checking.",
        ],
        "metric_definition": "Count fact_event rows joined to dim_reason where "
                             "capacity_driven=true AND actionable=true; count events, not people.",
        "ranking": "Metric descending, then region_name ascending; round displayed values once.",
        "features": config["features"],
        "scope": config["scope"],
        "deployment": config["deployment"],
        "research": config.get("research", {}),
    }


def ontology_contract(config):
    require_proposal(config)
    if config["version"] == 2:
        from .flexible_artifacts import ontology_contract as flexible
        return flexible(config)
    schema = config["deployment"]["schema"]
    entities = [
        ("Region", "dim_region", "region_id"),
        ("Location", "dim_location", "location_id"),
        ("Resource", "dim_resource", "resource_id"),
        ("Reason", "dim_reason", "reason_id"),
        ("OperationalEvent", "fact_event", "event_id"),
        ("FinancialContext", "fact_finance", "finance_id"),
        ("RiskContext", "fact_risk", "risk_id"),
    ]
    relationships = [
        ("locatedIn", "Location", "Region", "region_id"),
        ("occurredAt", "OperationalEvent", "Location", "location_id"),
        ("requestsResource", "OperationalEvent", "Resource", "resource_id"),
        ("hasOutcomeReason", "OperationalEvent", "Reason", "reason_id"),
        ("financialContextIn", "FinancialContext", "Region", "region_id"),
        ("riskContextIn", "RiskContext", "Region", "region_id"),
    ]
    return {
        "schema": schema, "generation": 2,
        "entities": [{"name": n, "table": t, "key": k} for n, t, k in entities],
        "relationships": [
            {"name": n, "source": s, "target": t, "source_fk": fk}
            for n, s, t, fk in relationships
        ],
        "rules": [
            "Actionable capacity exceptions require both reason flags.",
            "Aggregate each fact independently to region before combining contextual measures.",
            "Risk context is undated; do not imply it is a quarterly observation.",
            "Financial amounts are integer cents; divide by 100 for display only.",
            "All data and operational policies are illustrative.",
        ],
        "authoring_notes": [
            "This JSON is an authoring contract, NOT a Fabric ontology definition.",
            "Use the current ontology skill and validate supported generation-2 API/TMDL.",
            "Use dedicated /ontologies create/updateDefinition endpoints, not Ontology Agent.",
            "Use business-friendly entity, ontology relationship name/label and rule names before final native rebinding; keep technical physical join IDs separate and update rule relationship references.",
            "After the final API write, inspect every entity's source identity, Properties mappings and graph eligibility. Reselect Source column from its existing bound lakehouse table only for unresolved mappings; save and reverify. Never skip inspection.",
            "Preserve native lakehouse partition annotations; see docs/ontology-bindings.md for the observed eight-annotation recipe and its limits.",
            "Persist lineage tags per run; diff portal-written bindings before updateDefinition.",
            "No Decimal graph properties: money is int64 cents.",
            "After portal refresh, verify edge counts and properties through actual GQL.",
        ],
    }


def analytical_sql(config):
    require_proposal(config)
    if config["version"] == 2:
        from .flexible_artifacts import analytical_sql as flexible
        return flexible(config)
    s = config["deployment"]["schema"]
    return f"""-- Synthetic aggregates only. No fact-to-fact joins.
CREATE OR ALTER VIEW [{s}].[vw_demo_region_period] AS
WITH events AS (
    SELECT e.region_id, YEAR(e.event_date) AS year, DATEPART(quarter,e.event_date) AS quarter,
           COUNT_BIG(*) AS events,
           SUM(CASE WHEN r.capacity_driven=1 AND r.actionable=1 THEN 1 ELSE 0 END) AS actionable_events
    FROM [{s}].[fact_event] e
    JOIN [{s}].[dim_reason] r ON r.reason_id=e.reason_id
    GROUP BY e.region_id, YEAR(e.event_date), DATEPART(quarter,e.event_date)
), finance AS (
    SELECT region_id, YEAR(service_month) AS year, DATEPART(quarter,service_month) AS quarter,
           SUM(amount_cents) AS amount_cents
    FROM [{s}].[fact_finance]
    GROUP BY region_id, YEAR(service_month), DATEPART(quarter,service_month)
), risk AS (
    SELECT region_id, SUM(assessed) AS assessed, SUM(high_risk) AS high_risk
    FROM [{s}].[fact_risk] GROUP BY region_id
), periods AS (
    SELECT DISTINCT YEAR([date]) AS year, DATEPART(quarter,[date]) AS quarter
    FROM [{s}].[dim_date]
)
SELECT d.region_id, d.region_name, p.year, p.quarter,
       COALESCE(e.events,0) AS events, COALESCE(e.actionable_events,0) AS actionable_events,
       COALESCE(f.amount_cents,0) AS amount_cents,
       k.assessed, k.high_risk,
       100.0*k.high_risk/NULLIF(k.assessed,0) AS high_risk_pct
FROM [{s}].[dim_region] d CROSS JOIN periods p
LEFT JOIN events e ON e.region_id=d.region_id AND e.year=p.year AND e.quarter=p.quarter
LEFT JOIN finance f ON f.region_id=d.region_id AND f.year=p.year AND f.quarter=p.quarter
LEFT JOIN risk k ON k.region_id=d.region_id;
"""


def notebook(config):
    require_proposal(config)
    if config["version"] == 2:
        from .flexible_artifacts import notebook as flexible
        return flexible(config)
    runtime = dict(config, scenario_resources=SCENARIOS[config["scenario"]]["resources"])
    setup = (
        "import json\nimport calendar\nimport hashlib\nfrom datetime import date, timedelta\n"
        "from pyspark.sql import functions as F, types as T\n"
        f"config = json.loads({json.dumps(json.dumps(runtime))})\n"
        f"SCHEMA = {config['deployment']['schema']!r}\n"
        f"CONFIG_HASH = {digest(config)!r}\n"
        + inspect.getsource(data.build_data)
        + "\ntables, expected = build_data(config)\n"
    )
    execute = """
# Fail closed: this build never resets or overwrites a populated schema.
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{SCHEMA}`")
if spark.sql(f"SHOW TABLES IN `{SCHEMA}`").count():
    raise RuntimeError("Target schema is populated. Use a new demo schema; do not reset it.")

def frame(rows):
    sample = rows[0]
    types = {str: T.StringType(), bool: T.BooleanType(), int: T.LongType()}
    schema = T.StructType([T.StructField(key, types[type(value)], False)
                           for key, value in sample.items()])
    result = spark.createDataFrame(rows, schema)
    for column in ("event_date", "service_month", "date"):
        if column in result.columns:
            result = result.withColumn(column, F.to_date(F.col(column)))
    return result

def save(name, value):
    value.write.format("delta").mode("errorifexists").saveAsTable(f"{SCHEMA}.{name}")

for name in ("events", "finance", "risk"):
    rows = tables[f"bronze_{name}"]
    raw_path = f"Files/demo_accelerator/{SCHEMA}/{CONFIG_HASH[:12]}/{name}"
    # Actual source-shaped raw JSON, then parse the landed files to bronze.
    frame(rows).coalesce(1).write.mode("errorifexists").json(raw_path)
    raw = spark.read.schema(frame(rows).schema).json(raw_path)
    save(f"bronze_{name}", raw)

bronze = spark.table(f"{SCHEMA}.bronze_events")
locations = frame(tables["dim_location"])
valid = bronze.join(locations.select("location_id"), "location_id", "left_semi")
save("silver_events", valid.dropDuplicates(["event_id"]))
save("silver_rejected_events", bronze.join(locations.select("location_id"), "location_id", "left_anti"))
for name in ("finance", "risk"):
    save(f"silver_{name}", spark.table(f"{SCHEMA}.bronze_{name}"))
for name in ("dim_region", "dim_location", "dim_resource", "dim_reason", "dim_date"):
    save(name, frame(tables[name]))
for source, target in (("events", "fact_event"), ("finance", "fact_finance"), ("risk", "fact_risk")):
    save(target, spark.table(f"{SCHEMA}.silver_{source}"))

lineage = []
for name in tables:
    if name.startswith("bronze_"):
        source = "Raw JSON Files"
    elif name.startswith("silver_"):
        source = "bronze_events" if name == "silver_rejected_events" else name.replace("silver_", "bronze_")
    elif name.startswith("fact_"):
        source = name.replace("fact_", "silver_")
    else:
        source = "Synthetic reference generator"
    lineage.append({"table_name": name, "source": source, "classification": "Synthetic demo only"})
save("meta_lineage", frame(lineage))
catalog = [{"table_name": name, "row_count": spark.table(f"{SCHEMA}.{name}").count(),
            "classification": "Synthetic demo only"} for name in list(tables) + ["meta_lineage"]]
catalog.append({"table_name": "meta_dictionary", "row_count": len(catalog) + 1,
                "classification": "Synthetic demo only"})
save("meta_dictionary", frame(catalog))

# Exact checks execute inside the durable notebook job before it can complete.
for name, rows in tables.items():
    assert spark.table(f"{SCHEMA}.{name}").count() == len(rows), f"Count mismatch: {name}"
for fact, column, dimension in (
    ("fact_event", "location_id", "dim_location"),
    ("fact_event", "region_id", "dim_region"),
    ("fact_event", "resource_id", "dim_resource"),
    ("fact_event", "reason_id", "dim_reason"),
    ("fact_finance", "region_id", "dim_region"),
    ("fact_risk", "region_id", "dim_region"),
):
    missing = spark.table(f"{SCHEMA}.{fact}").join(
        spark.table(f"{SCHEMA}.{dimension}").select(column), column, "left_anti").count()
    assert missing == 0, f"Broken FK: {fact}.{column}"
events = spark.table(f"{SCHEMA}.fact_event")
actual = events.join(spark.table(f"{SCHEMA}.dim_reason"), "reason_id").filter(
    F.col("capacity_driven") & F.col("actionable")).count()
assert actual == expected["actionable_events"], "Actionable metric mismatch"
money = spark.table(f"{SCHEMA}.fact_finance").agg(F.sum("amount_cents")).first()[0]
assert money == expected["finance_cents"], "Money reconciliation failed"
for fact, column in (("fact_event", "event_date"), ("fact_finance", "service_month")):
    assert spark.table(f"{SCHEMA}.{fact}").join(
        spark.table(f"{SCHEMA}.dim_date").select(F.col("date").alias(column)),
        column, "left_anti").count() == 0, "Missing date dimension key"
latest_year = int(expected["latest_quarter"][:4])
latest_quarter = int(expected["latest_quarter"][-1])
quarter_events = events.filter((F.year("event_date") == latest_year) &
                              (F.quarter("event_date") == latest_quarter))
assert quarter_events.count() == expected["latest_quarter_events"], "Quarter count mismatch"
quarter_actionable = quarter_events.join(spark.table(f"{SCHEMA}.dim_reason"), "reason_id").filter(
    F.col("capacity_driven") & F.col("actionable")).count()
assert quarter_actionable == expected["latest_quarter_actionable"], "Quarter metric mismatch"
assert spark.table(f"{SCHEMA}.meta_dictionary").count() == len(tables) + 2, "Catalog incomplete"
print(json.dumps({"config_hash": CONFIG_HASH, "verified": True, "expected": expected}))
"""
    cells = [
        {"cell_type": "markdown", "metadata": {}, "source": [
            "# Synthetic customer demo\n",
            "Submitted notebook job only. No interactive Livy execution. ",
            "Never resets a populated schema. All upstream systems are simulated.\n",
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


def semantic_contract(config):
    require_proposal(config)
    if config["version"] == 2:
        from .flexible_artifacts import semantic_contract as flexible
        return flexible(config)
    return {
        "enabled": config["features"]["semantic_model"],
        "planning": config["features"]["planning"],
        "preferred_mode": "DirectLake",
        "fallback": "Import only after explicit approval and a Planning compatibility check",
        "tables": ["dim_region", "dim_location", "dim_resource", "dim_reason", "dim_date",
                   "fact_event", "fact_finance", "fact_risk"],
        "relationships": [
            ["fact_event", "region_id", "dim_region", "region_id"],
            ["fact_event", "location_id", "dim_location", "location_id"],
            ["fact_event", "resource_id", "dim_resource", "resource_id"],
            ["fact_event", "reason_id", "dim_reason", "reason_id"],
            ["fact_event", "event_date", "dim_date", "date"],
            ["fact_finance", "region_id", "dim_region", "region_id"],
            ["fact_finance", "service_month", "dim_date", "date"],
            ["fact_risk", "region_id", "dim_region", "region_id"],
        ],
        "measures": {
            "Events": "COUNTROWS(fact_event)",
            "Actionable Events": "CALCULATE([Events], dim_reason[capacity_driven] = TRUE(), "
                                 "dim_reason[actionable] = TRUE())",
            "Financial Amount": "DIVIDE(SUM(fact_finance[amount_cents]), 100)",
            "Assessed": "SUM(fact_risk[assessed])",
            "High Risk": "SUM(fact_risk[high_risk])",
            "High Risk %": "DIVIDE([High Risk], [Assessed])",
        },
        "notes": [
            "Model contract, not deployed TMDL. Author against verified gold table schema.",
            "Use single-direction many-to-one relationships; no dim_location-to-dim_region "
            "relationship in this model to avoid an ambiguous path.",
            "Mark dim_date as a date table and its date column as key; hide foreign keys.",
            "Format High Risk % as percentage: DAX is a fraction, SQL high_risk_pct is 0..100.",
            "Risk is undated; date filtering must not imply a dated assessment.",
            "Reconcile every measure, including selected-quarter figures, against expected.json.",
            "Validate viewer access and credentials; stop on credential errors.",
            "Keep model identity stable once bound to a Plan item.",
        ],
        "planning_steps": [
            "Confirm feature availability, capacity and model compatibility before promising Planning.",
            "Approve a dedicated SQL writeback database (not the Rayfin app database).",
            "Create the Plan item and bind the model using current supported UI/API.",
            "Smoke-test one measure; stop if Direct Lake is unsupported and seek approval for Import.",
            "Let Planning create destination tables; configure write permissions in the portal.",
            "Save an illustrative scenario, read back its rows and reconcile the changed values.",
        ],
    }


def generate(config, root):
    if existing_mode(config):
        from .existing_data import generate as existing
        return existing(config, Path(root), write_json)
    root = Path(root)
    require_proposal(config)
    if config["version"] == 2:
        from .flexible_artifacts import generate as flexible
        return flexible(config, root, write_json, operator_guide)
    scenario = SCENARIOS[config["scenario"]]
    runtime = dict(config, scenario_resources=scenario["resources"])
    tables, expected = data.build_data(runtime)
    write_json(root / "config.json", config)
    write_json(root / "scenario.json", scenario_contract(config))
    write_json(root / "ontology-contract.json", ontology_contract(config))
    write_json(root / "semantic-model-contract.json", semantic_contract(config))
    write_json(root / "expected.json", expected)
    write_json(root / "notebooks" / "build_demo.ipynb", notebook(config))
    for name, rows in tables.items():
        write_json(root / "preview" / f"{name}.json", rows)
    (root / "aggregate-views.sql").write_text(analytical_sql(config), encoding="utf-8")
    instructions = f"""# Data agent authoring contract

Customer: {config['customer']['name']}
Audience: {config['audience']}
Primary question: {scenario['question']}

Use the ontology for business meaning and the lakehouse for T-SQL answers.
Only query schema {config['deployment']['schema']}. Return regional aggregates only.
Use fact_event joined to dim_reason; capacity_driven=1 AND actionable=1 defines the headline.
Count events, not people. Aggregate facts separately by region before joining.
Filter event_date and service_month to the same period. Risk is undated; disclose this.
Use expected.json's latest quarter; label it partial unless latest_quarter_is_complete is true.
Order ranks by metric DESC then region_name ASC. Round display values exactly once.
SQL must return every metric in the answer. Keep tool requests below 1,000 characters.
Do not claim causal effects, real customer outcomes, production governance or live ingestion.
All records are synthetic; financial meaning is: {scenario['finance']}.
Do not expose source-level identifiers in answers.

Publishing description: Return the data agent's output as-is without summarizing,
rephrasing or adding interpretation. Confirm that this is preserved on publication.

Configure selected gold
tables/columns, instructions and checked examples using current supported tools.
After creation, the operator must open errored draft examples, make a safe edit
(such as appending a newline and an empty SQL comment --), save and verify that
validation clears. Preserve SQL semantics; do not hide executable SQL in comments
or assume re-saving guarantees a fix. Record portal validation separately from SQL.
Required sequence: lakehouse first -> repair draft examples -> publish SQL-only
agent in preview runtime -> manually add ontology -> publish again.
Both publications require approval. Capture a bounded SQL-only answer baseline
after the first publication. Add ontology context manually in the portal:
Sources -> Add sources -> Add an ontology. This is a required operator step,
not an automated adapter. Verify examples remain error-free after the second
publication and repeat the answer sample; validation alone does not prove accuracy.
Select facts and supporting business/calendar/period dimensions from the approved
analytical model, not just the focused ontology projection. Enable scenario-relevant
slicing, combined dimension filters, grouping and drill-down along valid relationships.
Verify columns against live SQL and include dimension-join examples; do not invent
attribution, multiply fact rows or silently drop unmatched alternate date roles.
Test draft and published independently; published example validation is a known
historical issue, NOT proof the runtime will use the examples.
"""
    (root / "data-agent-instructions.md").write_text(instructions, encoding="utf-8")
    graph = """// Proposed entity/property names: verify deployed names before executing.
MATCH (e:OperationalEvent)-[:hasOutcomeReason]->(r:Reason),
      (e)-[:occurredAt]->(:Location)-[:locatedIn]->(g:Region)
FILTER r.CapacityDriven AND r.Actionable
RETURN g.RegionName AS region, count(*) AS actionable_events
GROUP BY region
ORDER BY actionable_events DESC, region

// Separate topology check
MATCH ()-[e]->()
RETURN labels(e) AS relationship, count(*) AS edges
GROUP BY relationship
"""
    (root / "graph-query-patterns.gql").write_text(graph, encoding="utf-8")
    app = {
        "enabled": config["features"]["app"],
        "story": ["See the operational problem", "Explore trends and regional context",
                  "Ask the data agent why it matters", "Record an owned response"],
        "live_analytics": "fabric-sqlanalytics connector over vw_demo_region_period only",
        "snapshot_fallback": "Explicit approval required; label the snapshot and its export time",
        "action_entity": {
            "fields": ["id", "region_id", "period", "title", "assignee", "status", "note",
                       "owner_id", "createdAt", "updatedAt"],
            "statuses": ["Proposed", "In progress", "Blocked", "Done"],
            "permissions": "Authenticated read; create/update/delete only for claims.sub = owner_id",
        },
        "safety": [
            "Analytics connector exposes only aggregate views, never base fact tables.",
            "Application-authenticated reads run as the app owner; disclose this explicitly.",
            "Permissions must be enforced by the data service, not just hidden UI controls.",
            "Action log is live in its own app database, not the Planning writeback database.",
            "Action writeback does NOT update the ontology or data agent in this version.",
            "An unavailable log must never be shown as no actions recorded.",
        ],
        "checks": ["typecheck", "build", "lint", "tests", "visual validation",
                   "Rayfin findUnparseableScripts returns []", "signed-in deployed connector reads",
                   "create/reload/update/delete a throwaway action", "second-user ownership refusal"],
    }
    write_json(root / "app-contract.json", app)
    (root / "OPERATOR.md").write_text(operator_guide(config), encoding="utf-8")
    return expected


def operator_guide(config):
    if config["version"] == 2:
        design = (
            "The synthetic schema and workload follow proposal.tables. Count Delta tables dynamically "
            "(declared tables plus two governance tables); raw bronze extracts are Files, not Delta tables. "
            "Review each table's purpose/grain/source, key relationships, transformation, row bound and "
            "metrics. Validate the physical-row budget, not an arbitrary table quota."
        )
        if config["proposal"].get("reporting"):
            design += " Reporting constraints: " + config["proposal"]["reporting"]["notes"]
        research = (
            "Use the customer website, audience and described sources to suggest 2-3 use cases in Chat. "
            "Recommend a use case and its synthetic schema; cite public sources, distinguish facts from "
            "inferences, and ask the user to select/approve. No industry allowlist or fixed table count. "
            "The selected proposal drives all downstream artifacts. Record industry confirmation and "
            "research evidence before the story gate. See docs/flexible-proposals.md."
        )
    else:
        design = "Legacy reference schema; its table count is an example, not a platform requirement."
        research = (
            "This version-1 scenario is an opt-in regression example. Use version-2 intake for new "
            "customer industries and flexible schemas. Research public sources and confirm assumptions."
        )
    return f"""# Customer demo run: {config['customer']['name']}

This is a guided Copilot/operator workflow, not an unattended full-stack deployment.
Only the data-stage adapter is automated. IQ, semantic model, Planning and
Rayfin authoring/deployment require the current specialist skills and recorded evidence.
Contracts are NOT Fabric item definitions. No generated JSON contract can be POSTed as an item.

## 1. Research and story gate
{research}
Do not infer internal systems as fact. Review all scenario.json assumptions.
The CLI does not contain an embedded LLM/crawler; Copilot performs proposal research.
Unsupported declarative recipes must be implemented/tested, not silently approximated.

## 2. Design gate
Review scenario.json, expected.json, ontology-contract.json, app-contract.json and
semantic-model-contract.json. {design}
Review raw -> bronze -> silver -> gold notebook and read-only previews.
Approve scope, costs, feature availability, workspace and fresh schema. No real data.

## 3. Data gate (automated)
Approve data-build, then run deploy-data. This may create a lakehouse and notebook,
then submits a durable RunNotebook job. Check jobs with deploy-data again after a
local timeout; never submit a second run. resume works from saved IDs.
Existing nonempty schemas fail; an incomplete build needs investigation and a new
schema/run, not an automatic reset. The notebook asserts counts, FKs and headline totals.
Wait for SQL endpoint metadata sync and independently verify expected.json using T-SQL.

## 4. Fabric IQ gate (specialist-assisted)
Use fabriciq-ontology-cli authoring and the CURRENT Fabric data-agent guidance.
Resolve current APIs, do not copy old undocumented routes blindly. Produce generation-2
TMDL from ontology-contract.json, including physical backing joins and business relationships.
Persist lineage tags. Use POST /v1/workspaces/{{workspaceId}}/ontologies for creation
and POST /v1/workspaces/{{workspaceId}}/ontologies/{{ontologyId}}/updateDefinition
for explicitly approved updates; do not use Ontology Agent in this flow.
Give entities, ontology relationship names AND labels, and rules business-friendly
names before deployment; the Relationship Types sidebar displays names, not labels.
Keep technical physical join IDs separate. Preserve lineage and update linked rule
references when renaming ontology elements. Finish naming/rule edits before rebinding.
Deploy once, diff readback. After the final API write, inspect each entity's
source identity, Bind data -> Properties mappings and graph eligibility.
If mappings remain unresolved, reselect the correct Source column from the
existing bound lakehouse table, Save and verify every mapping again. Do not
reselect already-correct properties merely to satisfy a checklist. Inspection
remains mandatory even when no repair is needed. See docs/ontology-bindings.md
for the observed native annotation recipe; definition readback alone is not
proof of effective bindings. Full-definition updates can remove repairs:
finish API edits first, then repeat inspection after any approved later update.
Materialize only after the applicable approval. Completion of a refresh is not proof:
query actual properties, relationship counts and aggregate parity with SQL.
Use the graph model's distinct ID with the approved direct GQL route
POST /v1/workspaces/{{workspaceId}}/graphModels/{{graphModelId}}/executeQuery?beta=true.
See docs/graph-query-handoff.md. An ontology-agent tool limitation is not proof
that this API is unavailable. If specialist guidance conflicts, stop for separate
approval of the reviewed public-API route; never silently switch execution paths.
Configure lakehouse source,
instructions and SQL examples. Select scenario-relevant facts and supporting business,
calendar and period dimensions from the approved analytical model, not just the
focused ontology projection. Verify the actual schema, date roles and valid filter
paths; demonstrate multi-dimensional slicing/grouping in live-checked examples.
Aggregate facts independently at matching grain; never multiply monthly budgets
by joining them to every calendar day.
After agent creation, manually repair errored draft examples: open each affected
example, append a newline and an empty SQL comment -- (or another safe edit),
save and verify validation clears without changing SQL semantics. Record the
portal result; direct SQL success alone does not clear this checkpoint.
Required sequence: lakehouse first -> repair draft examples -> publish SQL-only
agent in preview runtime -> manually add ontology -> publish again.
Both publications require approval. Preserve publishing description on both.
Capture a bounded SQL-only answer baseline after the first publication.
Add ontology to the agent manually: Sources -> Add sources -> Add an ontology.
Record operator confirmation separately from machine readback.
Do not retry the blocked ontology datasource-create route.
After the second publication, verify example errors remain cleared and repeat
a bounded answer sample against the pre-attachment baseline. Example validation
does not establish answer accuracy or ontology use.
Start with one capacity-health question, then a small bounded repeated sample, concurrency <=2.
Record SQL/graph parity and draft/published results separately, including known issues.
Do not claim a SQL answer proves graph execution. Do not retry through capacity throttling.
Optional SDK evaluation writes result tables: see docs/data-agent-evaluation.md.
Verify the SDK version, eval_result destination and both table collision checks
before an approved run. Do not substitute interactive success for durable-job
acceptance. Preserve session ownership and later CU measurement requirements.

## 5. Optional semantic model gate
Enabled: {config['features']['semantic_model']}.
Use semantic-model-authoring, first inspect the actual deployed gold schema.
The installed modeling MCP is for Fabric workspace models, not offline PBIP authoring.
Build the contract's tables/relationships/measures through the supported route; export
the verified definition for reuse. Do not hand-author TMDL when a supported MCP route works.
List before create and never blindly retry a create. Preserve identity on updates.
Reconcile DAX against expected.json, including declared period/business-key filters and money units.
Validate credentials and a second viewer; stop on credential errors.

## 6. Optional Planning gate
Enabled: {config['features']['planning']}.
Use semantic-model-contract.json planning_steps. Verify current Direct Lake support;
the original healthcare demo did NOT validate this. Ask before Import fallback.
Provision an approved separate writeback database only if needed. Let Planning create
its tables. Guide portal Plan/destination/permission setup where no API is available.
Keep model name/identity stable after binding. Save and read back a test scenario.

## 7. Optional Fabric App gate
Enabled: {config['features']['app']}.
Load rayfin-getting-started and generated in-project skills; consult installed CLI docs.
Review aggregate-views.sql SELECTs against expected.json BEFORE applying each view.
For version-2 proposals, execute GO-separated SQL batches separately.
Use the app-contract.json story and live aggregate connector; use a labelled snapshot
only with explicit approval. Rayfin dev and up both write Fabric resources.
Run its workspace-specific dry run before deployment; never --force or --yes.
Lower connector TC39 decorators, and run the actual built-bundle parseability gate.
A local stub/harness does not prove a connector. Have the operator sign in in their own
browser; verify deployed figures, real reads, persistence and server-side ownership.
Do not automate around interactive sign-in failures or manufacture user-owned seed rows.

## 8. Rehearsal gate
Start with story, ask one grounded question, show graph meaning and log a response.
Run a short smoke check, not a capacity-heavy suite before presenting.
Record resource links, baseline period, exact numbers, evidence, limitations,
manual steps and recovery instructions. Distinguish machine checks from owner attestation.
All gates need explicit approval. complete records an operator attestation, not a
machine verification; the CLI labels it accordingly. No deployment happens from complete.
"""
