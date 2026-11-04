import ast
import copy
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from demo_accelerator.artifacts import (
    analytical_sql, generate, notebook, ontology_contract, scenario_contract, semantic_contract,
)
from demo_accelerator.blueprint import column_map, ordered_tables, relationships
from demo_accelerator.cli import main
from demo_accelerator.config import DemoError, brief, load, validate
from demo_accelerator.discovery import research_brief
from demo_accelerator.flexible_artifacts import metric_views
from demo_accelerator.flexible_data import build_blueprint
from demo_accelerator.fabric import deploy_data
from demo_accelerator.state import REQUIRED_CHECKS, approve, complete, initialize, read


ROOT = Path(__file__).resolve().parents[1]


def insurance():
    return load(ROOT / "examples" / "insurance-claims.json")


def expand(config):
    """Five justified context extracts, each with a staging/curated lineage."""
    for domain in ("complaint", "reserve", "recovery", "renewal", "fraud_review"):
        raw = {
            "name": f"bronze_{domain}", "layer": "bronze", "source": 0, "rows": 20,
            "grain": f"One illustrative {domain} record", "purpose": f"Explain {domain} context",
            "key": "record_id",
            "columns": [
                {"name": "record_id", "type": "int64", "description": "Synthetic record key",
                 "generator": {"kind": "sequence"}},
                {"name": "policy_id", "type": "int64", "description": "Portfolio context",
                 "generator": {"kind": "reference", "table": "dim_policy", "column": "policy_id"}},
            ],
        }
        config["proposal"]["tables"].extend([
            raw,
            {"name": f"silver_{domain}", "layer": "silver", "from": f"bronze_{domain}",
             "grain": raw["grain"], "purpose": f"Normalize {domain}", "key": "record_id"},
            {"name": f"fact_{domain}", "layer": "gold", "from": f"silver_{domain}",
             "grain": raw["grain"], "purpose": f"Query {domain}", "key": "record_id"},
        ])
        config["proposal"]["metrics"].append({
            "name": f"{domain}_records", "label": f"Illustrative {domain} records",
            "table": f"fact_{domain}", "aggregation": "count", "group_by": ["policy_id"],
            "unit": "records", "interpretation": f"Recorded {domain} context by portfolio.",
        })
    return config


def utilities():
    """A distinct industry, question and schema, not labels over the claims model."""
    config = brief()
    config["proposal"] = {
        "industry": "Water utilities",
        "title": "Pump maintenance prioritization",
        "business_question": "Which treatment plants have critical pumps and outstanding work orders?",
        "audience_rationale": "Maintenance supervisors prioritize inspections and work assignment.",
        "decision": "Record an inspection response for a plant.",
        "assumptions": ["Fictional assets and readings, not a safety assessment or real telemetry."],
        "tables": [
            {"name": "dim_plant", "layer": "gold", "source": 0, "rows": 3, "key": "plant_key",
             "grain": "One treatment plant", "purpose": "Maintenance context",
             "columns": [
                 {"name": "plant_key", "type": "int64", "description": "Synthetic plant key",
                  "generator": {"kind": "sequence"}},
                 {"name": "plant_label", "type": "string", "description": "Fictional plant",
                  "generator": {"kind": "label", "prefix": "Illustrative plant"}},
             ]},
            {"name": "dim_pump", "layer": "gold", "source": 0, "rows": 12, "key": "pump_key",
             "grain": "One pump", "purpose": "Asset structure",
             "columns": [
                 {"name": "pump_key", "type": "int64", "description": "Synthetic pump key",
                  "generator": {"kind": "sequence", "start": 10}},
                 {"name": "plant_key", "type": "int64", "description": "Plant owning this pump",
                  "generator": {"kind": "reference", "table": "dim_plant", "column": "plant_key"}},
                 {"name": "critical", "type": "boolean", "description": "Illustrative asset criticality",
                  "generator": {"kind": "boolean", "true_percent": 30}},
             ]},
        ],
        "metrics": [
            {"name": "critical_pumps", "label": "Critical pump assets", "table": "dim_pump",
             "aggregation": "count", "filters": [{"column": "critical", "op": "eq", "value": True}],
             "group_by": ["plant_key"], "unit": "pumps", "interpretation": "Undated critical-asset inventory."}
        ],
    }
    for name in ("observation", "work_order"):
        config["proposal"]["tables"].extend([
            {"name": f"bronze_{name}", "layer": "bronze", "source": 0, "rows": 100,
             "grain": f"One {name}", "purpose": f"Source {name} extract", "key": "record_key",
             "columns": [
                 {"name": "record_key", "type": "int64", "description": "Synthetic row key",
                  "generator": {"kind": "sequence"}},
                 {"name": "pump_key", "type": "int64", "description": "Referenced pump",
                  "generator": {"kind": "reference", "table": "dim_pump", "column": "pump_key"}},
                 {"name": "recorded_date", "type": "date", "description": "Illustrative record date",
                  "generator": {"kind": "date"}},
                 {"name": "score", "type": "int64", "description": "Illustrative priority score",
                  "generator": {"kind": "integer", "min": 1, "max": 10}},
             ]},
            {"name": f"silver_{name}", "layer": "silver", "from": f"bronze_{name}",
             "grain": f"One valid {name}", "purpose": "Typed source validation", "key": "record_key"},
            {"name": f"fact_{name}", "layer": "gold", "from": f"silver_{name}",
             "grain": f"One valid {name}", "purpose": "Operational prioritization", "key": "record_key"},
        ])
        config["proposal"]["metrics"].append({
            "name": f"{name}_priority", "label": f"Average {name} priority",
            "table": f"fact_{name}", "aggregation": "avg", "column": "score", "group_by": ["pump_key"],
            "time_column": "recorded_date", "unit": "score", "interpretation": "Synthetic average, not equipment health.",
        })
    return config


class BriefTests(unittest.TestCase):
    def test_default_intake_has_no_industry_or_scenario(self):
        config = validate(brief())
        self.assertIsNone(config["proposal"])
        self.assertNotIn("scenario", config)
        task = research_brief(config)
        self.assertIsNone(task["table_count_constraint"])
        self.assertEqual(task["status"], "needs-research-and-proposal")

    def test_cli_default_init_and_plan(self):
        from contextlib import redirect_stdout
        from io import StringIO
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(StringIO()) as output:
            path = Path(temporary) / "intake.json"
            self.assertEqual(main(["init", "--output", str(path)]), 0)
            self.assertEqual(load(path)["version"], 2)
            output.seek(0)
            output.truncate()
            self.assertEqual(main(["plan", str(path)]), 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "needs-research-and-proposal")

    def test_cannot_generate_an_unproposed_customer(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(DemoError, "propose a use case"):
                generate(brief(), Path(root))
            self.assertFalse((Path(root) / "config.json").exists())

    def test_arbitrary_industry_and_more_sources_allowed(self):
        config = insurance()
        config["proposal"]["industry"] = "Specialty commercial leasing"
        config["sources"] = [f"System {i} and described data" for i in range(12)]
        validate(config)
        self.assertEqual(scenario_contract(config)["industry"], "Specialty commercial leasing")

    def test_explicit_research_remains_optional_until_story_approval(self):
        config = insurance()
        del config["research"]
        validate(config)
        self.assertEqual(scenario_contract(config)["research"], {})
        with tempfile.TemporaryDirectory() as temporary:
            generate(config, Path(temporary))
            self.assertTrue((Path(temporary) / "scenario.json").exists())

    def test_research_evidence_needed_at_story_gate(self):
        config = insurance()
        config["research"]["industry_confirmed"] = True
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generate(config, root)
            initialize(root, config)
            with self.assertRaisesRegex(DemoError, "research notes and cited"):
                approve(root, "story", "Approve")


class BlueprintTests(unittest.TestCase):
    def test_ten_and_twenty_five_table_designs(self):
        for config, count in ((insurance(), 10), (expand(insurance()), 25), (utilities(), 10)):
            with self.subTest(industry=config["proposal"]["industry"], count=count):
                validate(config)
                tables, expected = build_blueprint(config)
                self.assertEqual(expected["delta_table_count"], count)
                self.assertEqual(len(tables) + 2, count)
                self.assertEqual(tables, build_blueprint(copy.deepcopy(config))[0])
                self.assertTrue(all(c["missing"] == 0 for c in expected["referential_integrity"]))

    def test_all_artifacts_follow_proposal_not_healthcare(self):
        config = expand(insurance())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = generate(config, root)
            state = initialize(root, config)
            self.assertEqual(read(root)[1]["config_hash"], state["config_hash"])
            self.assertEqual(expected["delta_table_count"], 25)
            self.assertEqual(len(list((root / "preview").glob("*.json"))), 23)
            ontology = ontology_contract(config)
            gold = {t["name"] for t in config["proposal"]["tables"] if t["layer"] == "gold"}
            self.assertEqual({e["table"] for e in ontology["entities"]}, gold)
            self.assertTrue(any(r["target"] == "dim_policy" for r in ontology["relationships"]))
            self.assertEqual(set(semantic_contract(config)["tables"]), gold)
            for name in ("data-agent-instructions.md", "ontology-contract.json", "app-contract.json",
                         "aggregate-views.sql", "semantic-model-contract.json"):
                text = (root / name).read_text(encoding="utf-8")
                for forbidden in ("fact_event", "dim_region", "SdohRisk", "vw_demo_region_period"):
                    self.assertNotIn(forbidden, text)

    def test_raw_budget_counts_copies_and_governance(self):
        config = insurance()
        tables, expected = build_blueprint(config)
        raw = sum(len(tables[t["name"]]) for t in config["proposal"]["tables"] if t["layer"] == "bronze")
        self.assertEqual(expected["physical_rows"], sum(map(len, tables.values())) + raw + 2 * len(tables) + 3)
        config["scope"]["max_total_rows"] = expected["physical_rows"] - 1
        with self.assertRaisesRegex(DemoError, "workload upper bound"):
            validate(config)
        config["scope"]["max_total_rows"] += 1
        validate(config)

    def test_dependency_order_ignores_input_order(self):
        config = insurance()
        expected = build_blueprint(config)
        config["proposal"]["tables"].reverse()
        validate(config)
        self.assertEqual(build_blueprint(config), expected)

    def test_unsupported_recipe_is_not_silently_substituted(self):
        config = insurance()
        config["proposal"]["tables"][0]["columns"][0]["generator"] = {"kind": "eval", "code": "print('x')"}
        with self.assertRaisesRegex(DemoError, "unsupported generator"):
            validate(config)

    def test_invalid_schemas_fail_before_generation(self):
        mutations = [
            lambda c: c["proposal"]["tables"].append(copy.deepcopy(c["proposal"]["tables"][0])),
            lambda c: c["proposal"]["tables"][0].update(name="meta_custom"),
            lambda c: c["proposal"]["tables"][0].update(name="x; DROP TABLE gold"),
            lambda c: c["proposal"]["tables"][0].update(rows=10001),
            lambda c: c["proposal"]["tables"][0].update(key="missing"),
            lambda c: c["proposal"]["tables"][2]["columns"][1]["generator"].update(table="missing"),
            lambda c: c["proposal"]["tables"][2]["columns"][1].update(type="string"),
            lambda c: c["proposal"]["tables"][3].update(**{"from": "fact_claim"}),
            lambda c: c["proposal"]["metrics"][0].update(table="bronze_claim"),
            lambda c: c["proposal"]["metrics"][0].update(aggregation="median"),
            lambda c: c["proposal"]["metrics"][0].update(time_column="status"),
            lambda c: c["proposal"]["metrics"][0]["filters"][0].update(value=[1]),
            lambda c: c["proposal"]["metrics"][0].update(group_by=["policy_id", "policy_id"]),
            lambda c: c["proposal"]["tables"][0].update(layer=[]),
            lambda c: c["proposal"]["tables"][0]["columns"][0].update(type=[]),
            lambda c: c["proposal"]["metrics"][0].update(aggregation=[]),
            lambda c: c["proposal"]["metrics"][0]["filters"][0].update(op=[]),
        ]
        for mutate in mutations:
            config = insurance()
            mutate(config)
            with self.subTest(mutation=mutate), self.assertRaises(DemoError):
                validate(config)

    def test_nonunique_key_is_an_explicit_failure(self):
        config = insurance()
        config["proposal"]["tables"][0]["columns"][0]["generator"] = {"kind": "integer", "min": 1, "max": 1}
        validate(config)
        with self.assertRaisesRegex(ValueError, "not unique"):
            build_blueprint(config)

    def test_deduplication_deterministically_selects_first_full_row(self):
        config = insurance()
        raw = config["proposal"]["tables"][2]
        raw.pop("key")
        raw["columns"][0]["generator"] = {"kind": "choice", "values": [1, 2, 3]}
        tables, _ = build_blueprint(validate(config))
        bronze = tables["bronze_claim"]
        silver = tables["silver_claim"]
        for claim in silver:
            matches = [r for r in bronze if r["claim_id"] == claim["claim_id"]]
            columns = list(column_map(config["proposal"])["bronze_claim"])
            self.assertEqual(claim, min(matches, key=lambda row: tuple(row[c] for c in columns)))
        self.assertEqual(len(silver), 3)

    def test_empty_transformed_output_and_empty_metric(self):
        config = utilities()
        clean = next(t for t in config["proposal"]["tables"] if t["name"] == "silver_work_order")
        clean["filters"] = [{"column": "score", "op": "gt", "value": 20}]
        tables, expected = build_blueprint(validate(config))
        self.assertEqual(tables["fact_work_order"], [])
        self.assertIsNone(expected["metrics"]["work_order_priority"]["value"])
        nb = notebook(config)
        ast.parse("".join(nb["cells"][2]["source"]))
        count = copy.deepcopy(next(m for m in config["proposal"]["metrics"] if m["table"] == "fact_work_order"))
        count.update(name="work_order_count", aggregation="count")
        count.pop("column")
        config["proposal"]["metrics"].append(count)
        _, expected = build_blueprint(validate(config))
        self.assertEqual(expected["metrics"]["work_order_count"]["value"], 0)
        self.assertIn("COALESCE(COUNTROWS('fact_work_order'), 0)",
                      semantic_contract(config)["measures"]["work_order_count"]["expression"])

    def test_period_completeness_not_assumed(self):
        config = insurance()
        config["scope"]["end_date"] = "2026-08-15"
        _, expected = build_blueprint(config)
        self.assertFalse(expected["metrics"]["open_claims"]["latest_quarter"]["complete"])
        config["scope"]["end_date"] = "2026-09-30"
        config["scope"]["months"] = 1
        _, expected = build_blueprint(config)
        self.assertFalse(expected["metrics"]["open_claims"]["latest_quarter"]["complete"])

    def test_view_alias_collisions_are_rejected(self):
        config = insurance()
        extra = copy.deepcopy(config["proposal"]["metrics"][0])
        extra["name"] += "_period"
        config["proposal"]["metrics"].append(extra)
        with self.assertRaisesRegex(DemoError, "view name collision"):
            validate(config)
        config = insurance()
        extra = copy.deepcopy(config["proposal"]["tables"][0])
        extra["name"] = "vw_open_claims"
        config["proposal"]["tables"].append(extra)
        with self.assertRaisesRegex(DemoError, "view name collision"):
            validate(config)
        config = insurance()
        config["proposal"]["metrics"][0]["name"] = "demo_year"
        with self.assertRaisesRegex(DemoError, "aliases"):
            validate(config)

    def test_integer_choices_must_fit_the_exact_numeric_range(self):
        config = insurance()
        config["proposal"]["tables"][0]["columns"][0]["generator"] = {
            "kind": "choice", "values": [2**53],
        }
        with self.assertRaisesRegex(DemoError, "integer choices"):
            validate(config)

    def test_sum_upper_bound_cannot_overflow_runtime_or_app(self):
        config = insurance()
        payment = next(t for t in config["proposal"]["tables"] if t["name"] == "bronze_payment")
        money = next(c for c in payment["columns"] if c["name"] == "amount_cents")
        money["generator"]["max"] = 2**53 - 1
        with self.assertRaisesRegex(DemoError, "aggregate upper bound"):
            validate(config)
        config = utilities()
        work = next(t for t in config["proposal"]["tables"] if t["name"] == "bronze_work_order")
        score = next(c for c in work["columns"] if c["name"] == "score")
        score["generator"]["max"] = 2**53 - 1
        with self.assertRaisesRegex(DemoError, "aggregate upper bound"):
            validate(config)

    def test_generated_setup_matches_local_generator(self):
        for config in (insurance(), expand(insurance()), utilities()):
            nb = notebook(validate(config))
            for cell in nb["cells"]:
                if cell["cell_type"] == "code":
                    ast.parse("".join(cell["source"]))
            source = "".join(nb["cells"][1]["source"]).replace(
                "from pyspark.sql import functions as F, types as T, Window\n", "")
            namespace = {}
            exec(compile(source, "<blueprint-setup>", "exec"), namespace)
            self.assertEqual((namespace["tables"], namespace["expected"]), build_blueprint(config))
            self.assertNotIn("== 17", "".join(nb["cells"][2]["source"]))

    @unittest.skipUnless(importlib.util.find_spec("nbformat"), "Install .[dev] for schema checks")
    def test_notebook_schema(self):
        import nbformat
        for config in (insurance(), expand(insurance()), utilities()):
            nbformat.validate(nbformat.from_dict(notebook(config)))

    def test_views_and_dax_use_same_filters_and_units(self):
        config = insurance()
        sql = analytical_sql(config)
        self.assertIn("[status] IN ('Open', 'Awaiting documents')", sql)
        self.assertIn("SUM([amount_cents])", sql)
        dax = semantic_contract(config)["measures"]
        self.assertIn("'fact_claim'[status] IN", dax["open_claims"]["expression"])
        self.assertEqual(dax["settlement_cents"]["unit"], "cents")
        self.assertNotIn("DIVIDE", dax["settlement_cents"]["expression"])

    def test_generated_sql_exact_metric_group_and_period_parity(self):
        quoted = insurance()
        claim = next(t for t in quoted["proposal"]["tables"] if t["name"] == "bronze_claim")
        status = next(c for c in claim["columns"] if c["name"] == "status")
        status["generator"]["values"] = ["Owner's review", 'Needs "evidence"', "Closed"]
        quoted["proposal"]["metrics"][0]["filters"][0]["value"] = ["Owner's review", 'Needs "evidence"']
        for config in (insurance(), expand(insurance()), utilities(), quoted):
            tables, expected = build_blueprint(validate(config))
            schema = config["deployment"]["schema"]
            with closing(sqlite3.connect(":memory:")) as sql:
                sql.execute(f"ATTACH DATABASE ':memory:' AS {schema}")
                sql.create_function("YEAR", 1, lambda d: int(d[:4]))
                sql.create_function("DATEPART", 2, lambda part, d: (int(d[5:7]) - 1) // 3 + 1)
                for name, rows in tables.items():
                    columns = list(column_map(config["proposal"])[name])
                    sql.execute(f"CREATE TABLE {schema}.{name} ({', '.join('[' + c + ']' for c in columns)})")
                    sql.executemany(f"INSERT INTO {schema}.{name} VALUES ({','.join('?' for _ in columns)})",
                                    [[row[c] for c in columns] for row in rows])
                for view in metric_views(config):
                    query = view["sql"].replace("CREATE OR ALTER VIEW", "CREATE VIEW").replace(
                        "COUNT_BIG", "COUNT").replace("DATEPART(quarter,", "DATEPART('quarter',")
                    sql.execute(query)
                    cursor = sql.execute(f"SELECT * FROM {schema}.{view['name']}")
                    columns = [item[0] for item in cursor.description]
                    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    baseline = expected["metrics"][view["metric"]]
                    if not view["period"]:
                        if baseline["groups"]:
                            self.assertEqual(sorted(rows, key=repr), sorted(baseline["groups"], key=repr))
                        else:
                            self.assertEqual(rows[0][view["metric"]], baseline["value"])
                    else:
                        quarter = baseline["latest_quarter"]
                        year, q = int(quarter["period"][:4]), int(quarter["period"][-1])
                        # count/sum are additive; averages require per-group parity, not summing averages.
                        metric = next(m for m in config["proposal"]["metrics"] if m["name"] == view["metric"])
                        selected = [r for r in rows if r["demo_year"] == year and r["demo_quarter"] == q]
                        if metric["aggregation"] in ("count", "sum"):
                            self.assertEqual(sum(r[view["metric"]] for r in selected), quarter["value"])

    def test_v2_uses_existing_approval_and_durable_job_adapter(self):
        from test_accelerator import FakeFabric
        config = insurance()
        config["research"].update(industry_confirmed=True, references=["https://example.com"])
        config["deployment"]["workspace_name"] = "Approved demo workspace"
        fake = FakeFabric()
        fake.status = "Completed"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generate(config, root)
            state = initialize(root, config)
            for gate in ("story", "design"):
                approve(root, gate, "Synthetic integration-test approval")
                complete(root, gate, {
                    "config_hash": state["config_hash"], "notes": "Synthetic integration test only",
                    "references": ["https://example.com"],
                    "checks": dict.fromkeys(REQUIRED_CHECKS[gate], True),
                })
            approve(root, "data-build", "Synthetic integration-test target approval")
            self.assertEqual(deploy_data(root, 0, fake)["status"], "Completed")
            import base64
            nb = json.loads(base64.b64decode(fake.posts[0][1]["definition"]["parts"][0]["payload"]))
            self.assertIn("build_blueprint", "".join(nb["cells"][1]["source"]))
            self.assertNotIn("fact_event", "".join(nb["cells"][2]["source"]))
            self.assertEqual(read(root)[1]["gates"]["data-build"]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
