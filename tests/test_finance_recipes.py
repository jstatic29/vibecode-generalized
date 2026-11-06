import ast
import copy
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

from demo_accelerator.artifacts import generate, notebook, semantic_contract, ontology_contract
from demo_accelerator.blueprint import column_map
from demo_accelerator.config import DemoError, load, validate
from demo_accelerator.flexible_artifacts import metric_views
from demo_accelerator.flexible_data import build_blueprint
from demo_accelerator.state import initialize, read, require_gate


ROOT = Path(__file__).resolve().parents[1]


def finance():
    return load(ROOT / "examples" / "project-finance.json")


def table(config, name):
    return next(t for t in config["proposal"]["tables"] if t["name"] == name)


def column(config, name, field):
    return next(c for c in table(config, name)["columns"] if c["name"] == field)


def sql_parity(test, config):
    tables, expected = build_blueprint(validate(config))
    schema = config["deployment"]["schema"]
    with closing(sqlite3.connect(":memory:")) as sql:
        sql.execute(f"ATTACH DATABASE ':memory:' AS {schema}")
        sql.create_function("YEAR", 1, lambda d: int(d[:4]))
        sql.create_function("MONTH", 1, lambda d: int(d[5:7]))
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
            names = [c[0] for c in cursor.description]
            observed = [dict(zip(names, row)) for row in cursor.fetchall()]
            baseline = expected["metrics"][view["metric"]]
            if view["period"]:
                wanted = baseline["periods"]
            else:
                defs = {m["name"]: m for m in config["proposal"]["metrics"]}
                for m in config["proposal"].get("derived_metrics", []):
                    defs[m["name"]] = defs[m["left"]]
                wanted = baseline["groups"] if defs[view["metric"]].get("group_by") else [
                    {view["metric"]: baseline["value"]}]
            test.assertEqual(sorted(observed, key=repr), sorted(wanted, key=repr), view["name"])
    return expected


class FinanceRecipeTests(unittest.TestCase):
    def test_calendar_grid_and_physical_budget(self):
        config = finance()
        tables, expected = build_blueprint(config)
        dates = [r["date"] for r in tables["dim_date"]]
        self.assertEqual(len(dates), 365)
        self.assertEqual(dates[0], "2025-11-01")
        self.assertEqual(dates[-1], "2026-10-31")
        self.assertTrue(all(date.fromisoformat(b) - date.fromisoformat(a) == timedelta(days=1)
                            for a, b in zip(dates, dates[1:])))
        periods = {r["period_id"] for r in tables["dim_period"]}
        self.assertTrue(all(r["period_id"] in periods for r in tables["dim_date"]))
        self.assertEqual(len(periods), 12)
        self.assertEqual(len({(r["project_id"], r["cost_category_id"], r["budget_month_start"])
                              for r in tables["fact_budget"]}), 864)
        self.assertEqual(Counter(r["project_id"] for r in tables["fact_budget"]), dict.fromkeys(range(1, 13), 72))
        self.assertEqual(expected["delta_table_count"], 16)
        self.assertEqual(expected["physical_rows"], 14701)
        self.assertTrue(all(c["missing"] == 0 for c in expected["referential_integrity"]))

    def test_actual_allocations_exactly_reconcile_to_every_budget_cell(self):
        config = finance()
        tables, _ = build_blueprint(config)
        actual = defaultdict(list)
        for row in tables["fact_cost_posting"]:
            actual[row["budget_id"]].append(row)
        for budget in tables["fact_budget"]:
            rows = actual[budget["budget_id"]]
            self.assertIn(len(rows), (2, 3))
            self.assertEqual(sum(r["actual_cost_cents"] for r in rows),
                             budget["approved_budget_cents"] * budget["cost_factor_bps"] // 10000)
            self.assertLessEqual(max(r["actual_cost_cents"] for r in rows) -
                                 min(r["actual_cost_cents"] for r in rows), 1)
            self.assertTrue(all(r["project_id"] == budget["project_id"] and
                                r["cost_category_id"] == budget["cost_category_id"] and
                                r["posting_date"][:7] == budget["budget_month_start"][:7] for r in rows))

    def test_invoice_dates_states_balances_and_holds_are_coherent(self):
        tables, expected = build_blueprint(finance())
        for row in tables["fact_supplier_invoice"]:
            self.assertLessEqual(row["invoice_date"], "2026-10-31")
            self.assertLessEqual(row["invoice_date"], row["due_date"])
            self.assertGreaterEqual(row["paid_cents"], 0)
            self.assertLessEqual(row["paid_cents"], row["invoice_amount_cents"])
            self.assertEqual(row["open_balance_cents"], row["invoice_amount_cents"] - row["paid_cents"])
            self.assertEqual(row["is_on_hold"], row["review_status"] == "On hold")
            if row["is_on_hold"]:
                self.assertGreater(row["open_balance_cents"], 0)
                self.assertNotEqual(row["hold_reason"], "None")
            if row["review_status"] == "Paid":
                self.assertEqual(row["open_balance_cents"], 0)
        self.assertEqual(expected["metrics"]["held_invoice_count"]["value"], 100)

    def test_derived_values_quarter_completeness_and_sql_monthly_parity(self):
        expected = sql_parity(self, finance())
        m = expected["metrics"]
        variance = m["actual_cost_cents"]["value"] - m["approved_budget_cents"]["value"]
        self.assertEqual(m["cost_variance_cents"]["value"], variance)
        self.assertEqual(m["cost_variance_ratio"]["value"], variance / m["approved_budget_cents"]["value"])
        q = {r["period"]: r for r in m["cost_variance_cents"]["quarters"]}
        self.assertTrue(q["2026-Q3"]["complete"])
        self.assertFalse(q["2025-Q4"]["complete"])
        self.assertFalse(q["2026-Q4"]["complete"])
        self.assertFalse(m["cost_variance_cents"]["latest_quarter"]["complete"])
        self.assertTrue(all("demo_month" in r for r in m["cost_variance_cents"]["periods"]))
        signs = {r["cost_variance_cents"] > 0 for r in m["cost_variance_cents"]["groups"]}
        self.assertEqual(signs, {True, False})

    def test_missing_operands_and_zero_denominators_stay_null(self):
        config = finance()
        column(config, "bronze_budget", "approved_budget_cents")["generator"].update(min=0, max=0)
        m = sql_parity(self, config)["metrics"]
        self.assertIsNone(m["cost_variance_ratio"]["value"])
        self.assertTrue(all(r["cost_variance_ratio"] is None for r in m["cost_variance_ratio"]["periods"]))
        config = finance()
        table(config, "silver_cost_posting")["filters"] = [{"column": "project_id", "op": "ne", "value": 1}]
        m = sql_parity(self, config)["metrics"]
        missing = [r for r in m["cost_variance_cents"]["groups"] if r["project_id"] == 1]
        self.assertTrue(missing)
        self.assertTrue(all(r["cost_variance_cents"] is None for r in missing))
        self.assertIsNotNone(m["cost_variance_cents"]["value"])
        config = finance()
        table(config, "silver_cost_posting")["filters"] = [{"column": "project_id", "op": "gt", "value": 100}]
        m = sql_parity(self, config)["metrics"]
        self.assertIsNone(m["cost_variance_cents"]["value"])
        self.assertTrue(all(r["cost_variance_cents"] is None for r in m["cost_variance_cents"]["periods"]))

    def test_derived_scalar_views_without_group_or_period(self):
        config = finance()
        for metric in config["proposal"]["metrics"][:2]:
            metric.pop("time_column")
            metric.pop("period_grain")
            metric["group_by"] = []
        expected = sql_parity(self, config)
        self.assertIsNone(expected["metrics"]["cost_variance_cents"]["latest_quarter"])
        self.assertEqual(expected["metrics"]["cost_variance_ratio"]["groups"], [])

    def test_nonadditive_ratios_must_be_recomputed_from_components(self):
        tables, expected = build_blueprint(finance())
        periods = expected["metrics"]["cost_variance_ratio"]["periods"]
        average = sum(r["cost_variance_ratio"] for r in periods) / len(periods)
        self.assertNotAlmostEqual(average, expected["metrics"]["cost_variance_ratio"]["value"], places=6)
        self.assertTrue(tables["fact_cost_posting"])

    def test_reordered_tables_and_changed_seed_are_deterministic(self):
        config = finance()
        expected = build_blueprint(config)
        config["proposal"]["tables"].reverse()
        self.assertEqual(build_blueprint(validate(config)), expected)
        config["scope"]["seed"] += 1
        changed = build_blueprint(config)
        self.assertNotEqual(expected[0]["fact_budget"], changed[0]["fact_budget"])
        self.assertEqual(changed, build_blueprint(copy.deepcopy(config)))
        sql_parity(self, config)

    def test_calendar_handles_leap_year_and_rejects_stale_counts(self):
        config = finance()
        config["scope"].update(end_date="2024-02-29", months=1)
        table(config, "dim_date")["rows"] = 29
        table(config, "dim_period")["rows"] = 1
        for name in ("bronze_budget", "silver_budget", "fact_budget"):
            table(config, name).pop("unique_by")
        column(config, "bronze_budget", "project_id")["generator"]["stride"] = 6
        column(config, "bronze_budget", "cost_category_id")["generator"]["stride"] = 1
        table(config, "bronze_budget")["rows"] = 72
        tables, _ = build_blueprint(validate(config))
        self.assertEqual(tables["dim_date"][-1]["date"], "2024-02-29")
        table(config, "dim_date")["rows"] = 28
        with self.assertRaisesRegex(DemoError, "complete window"):
            validate(config)

    def test_invalid_recipes_and_metric_grains_fail_explicitly(self):
        mutations = [
            lambda c: column(c, "bronze_budget", "project_id")["generator"].update(stride=0),
            lambda c: column(c, "bronze_budget", "project_id")["generator"].update(mode="random"),
            lambda c: column(c, "bronze_cost_posting", "budget_id")["generator"].update(mode="random"),
            lambda c: table(c, "bronze_cost_posting").update(rows=100),
            lambda c: column(c, "bronze_cost_posting", "actual_cost_cents")["generator"].update(divisor=0),
            lambda c: column(c, "bronze_cost_posting", "actual_cost_cents")["generator"].update(via="missing"),
            lambda c: column(c, "bronze_cost_posting", "project_id")["generator"].update(column="missing"),
            lambda c: column(c, "bronze_supplier_invoice", "paid_cents")["generator"].update(column="open_balance_cents"),
            lambda c: column(c, "bronze_supplier_invoice", "hold_reason")["generator"]["cases"].append({"when": "Ready", "value": "Duplicate"}),
            lambda c: column(c, "bronze_supplier_invoice", "due_date")["generator"].update(min_days=-1),
            lambda c: column(c, "dim_date", "period_id")["generator"].update(part="day"),
            lambda c: column(c, "dim_date", "period_id")["references"].update(column="missing"),
            lambda c: table(c, "bronze_supplier_invoice")["checks"][1].update(other_column="supplier_id"),
            lambda c: table(c, "bronze_supplier_invoice")["checks"][1].update(value="2026-10-31"),
            lambda c: c["proposal"]["derived_metrics"][0].update(left="missing"),
            lambda c: c["proposal"]["derived_metrics"][0].update(right="held_invoice_count"),
            lambda c: c["proposal"]["metrics"][1].update(group_by=["project_id"]),
            lambda c: c["proposal"]["metrics"][1].update(period_grain="quarter"),
            lambda c: c["proposal"]["derived_metrics"][0].update(unit="dollars"),
            lambda c: c["proposal"]["derived_metrics"][1].update(unit="percent"),
            lambda c: c["proposal"]["derived_metrics"][1].update(operation="eval"),
            lambda c: c["proposal"]["reporting"].update(calendar_column="missing"),
        ]
        for mutate in mutations:
            config = finance()
            mutate(config)
            with self.subTest(mutation=mutate), self.assertRaises(DemoError):
                validate(config)

    def test_unmapped_case_and_duplicate_grid_are_runtime_errors(self):
        config = finance()
        column(config, "bronze_supplier_invoice", "hold_reason")["generator"]["cases"].pop()
        with self.assertRaisesRegex(ValueError, "no unique map case"):
            build_blueprint(validate(config))
        config = finance()
        column(config, "bronze_budget", "project_id")["generator"]["stride"] = 1
        with self.assertRaisesRegex(ValueError, "unique_by"):
            build_blueprint(validate(config))
        config = finance()
        column(config, "bronze_supplier_invoice", "paid_percent")["generator"]["cases"][0]["value"] = 150
        with self.assertRaisesRegex(ValueError, "row checks failed"):
            build_blueprint(validate(config))

    def test_unsafe_intermediate_arithmetic_is_rejected(self):
        config = finance()
        column(config, "dim_project", "cost_factor_bps")["generator"]["values"] = [2**53 - 1]
        with self.assertRaisesRegex(DemoError, "safe intermediate"):
            validate(config)
        config = finance()
        column(config, "bronze_supplier_invoice", "paid_percent")["generator"]["cases"][0]["value"] = 2**53
        with self.assertRaisesRegex(DemoError, "exact numeric range"):
            validate(config)

    def test_notebook_embeds_the_same_recipe_engine_and_assertions(self):
        config = finance()
        nb = notebook(config)
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                ast.parse("".join(cell["source"]))
        setup = "".join(nb["cells"][1]["source"]).replace(
            "from pyspark.sql import functions as F, types as T, Window\n", "")
        namespace = {}
        exec(compile(setup, "<finance-notebook>", "exec"), namespace)
        self.assertEqual((namespace["tables"], namespace["expected"]), build_blueprint(config))
        execution = "".join(nb["cells"][2]["source"])
        self.assertIn("Duplicate grain", execution)
        self.assertIn("Grouped metric mismatch", execution)
        self.assertIn("Derived metric mismatch", execution)

    @unittest.skipUnless(importlib.util.find_spec("nbformat"), "Install .[dev] for schema checks")
    def test_official_notebook_schema(self):
        import nbformat
        nbformat.validate(nbformat.from_dict(notebook(finance())))

    def test_contracts_and_gates_remain_consistent_and_undeployed(self):
        config = finance()
        model = semantic_contract(config)
        self.assertEqual(model["measures"]["cost_variance_ratio"]["expression"],
                         "DIVIDE([cost_variance_cents], [approved_budget_cents])")
        self.assertIn("ISBLANK", model["measures"]["cost_variance_cents"]["expression"])
        self.assertIn("KEEPFILTERS", model["measures"]["held_invoice_count"]["expression"])
        self.assertEqual(model["reporting"], config["proposal"]["reporting"])
        relations = ontology_contract(config)["relationships"]
        self.assertTrue(any(r["source"] == "fact_cost_posting" and r["target"] == "dim_project" for r in relations))
        self.assertFalse(any(r["source"].startswith("fact_") and r["target"].startswith("fact_") for r in relations))
        self.assertEqual(sum(r["source"] == "fact_cost_posting" and r["target"] == "dim_date" for r in relations), 1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generate(config, root)
            initialize(root, config)
            _, state = read(root)
            self.assertTrue(all(g["status"] == "pending" for g in state["gates"].values()))
            self.assertNotIn("planning", state["gates"])
            with self.assertRaisesRegex(DemoError, "prerequisite"):
                require_gate(state, "data-build", approved=True)
            app = json.loads((root / "app-contract.json").read_text(encoding="utf-8"))
            self.assertEqual(len(app["derived_metrics"]), 2)
            self.assertEqual(app["reporting"]["as_of_date"], "2026-10-31")
            guide = (root / "OPERATOR.md").read_text(encoding="utf-8")
            self.assertNotIn("region filters", guide)
            self.assertIn("complete-calendar-month", guide)
            self.assertIn("POST /v1/workspaces/{workspaceId}/ontologies", guide)
            self.assertIn("/ontologies/{ontologyId}/updateDefinition", guide)
            self.assertIn("do not use Ontology Agent", guide)
            self.assertIn("entity -> Bind data -> Properties -> Source column", guide)
            self.assertIn("Full-definition updates can remove these native repairs", guide)
            self.assertIn("ontology relationship names AND labels", guide)
            self.assertIn("Finish naming/rule edits before rebinding", guide)
            self.assertIn("approved analytical model, not just the", guide)
            self.assertIn("multi-dimensional slicing/grouping", guide)
            self.assertIn("Add ontology to the agent manually", guide)
            self.assertIn("Sources -> Add sources -> Add an ontology", guide)
            self.assertIn("manually repair errored draft examples", guide)
            self.assertIn("empty SQL comment --", guide)
            self.assertIn("Both publications require approval", guide)
            self.assertLess(guide.index("publish SQL-only"), guide.index("manually add ontology"))
            instructions = (root / "data-agent-instructions.md").read_text(encoding="utf-8")
            for table in config["proposal"]["tables"]:
                if table["layer"] == "gold":
                    self.assertIn(table["name"], instructions)
            self.assertIn("not just the focused ontology projection", instructions)
            self.assertIn("combined dimension filters", instructions)
            self.assertIn("Examples must demonstrate dimension joins", instructions)
            self.assertIn("do not multiply monthly facts", instructions)
            self.assertIn("alternate date roles fall outside the calendar", instructions)
            self.assertIn("add ontology context manually", instructions)
            self.assertIn("This attachment is not automated", instructions)
            self.assertIn("manually open errored draft examples", instructions)
            self.assertIn("record portal validation separately", instructions)
            self.assertIn("Both publications require approval", instructions)
            self.assertLess(instructions.index("publish SQL-only"), instructions.index("manually add ontology"))
            self.assertIn("after the second publication verify examples remain error-free", instructions)
            contract = json.loads((root / "ontology-contract.json").read_text(encoding="utf-8"))
            self.assertTrue(any("not Ontology Agent" in note for note in contract["authoring_notes"]))
            self.assertTrue(any("existing bound lakehouse table" in note
                                for note in contract["authoring_notes"]))
            self.assertTrue(any("business-friendly entity, ontology relationship name/label and rule names"
                                in note for note in contract["authoring_notes"]))


if __name__ == "__main__":
    unittest.main()
