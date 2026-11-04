import ast
import copy
import hashlib
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from demo_accelerator.artifacts import analytical_sql, generate, notebook, semantic_contract
from demo_accelerator.config import DemoError, SCENARIOS, digest, example, validate
from demo_accelerator.data import build_data
from demo_accelerator.fabric import Client, deploy_data, ensure_item, preflight
from demo_accelerator.state import (
    REQUIRED_CHECKS, approve, complete, initialize, locked, read, save,
)


def confirmed(scenario="healthcare-access"):
    config = example(scenario)
    config["deployment"]["workspace_name"] = "Approved demo workspace"
    config["research"] = {
        "industry_confirmed": True,
        "notes": "Fictional test scenario, explicitly selected by the operator",
        "references": ["https://example.com"],
    }
    return config


def runtime(config):
    return dict(config, scenario_resources=SCENARIOS[config["scenario"]]["resources"])


def report(state, gate):
    return {
        "config_hash": state["config_hash"], "notes": "Explicit synthetic test evidence",
        "references": ["https://example.com/verification"],
        "checks": dict.fromkeys(REQUIRED_CHECKS[gate], True),
    }


class ConfigTests(unittest.TestCase):
    def test_examples_are_valid(self):
        for scenario in SCENARIOS:
            self.assertEqual(validate(example(scenario))["scenario"], scenario)

    def test_planning_requires_model(self):
        config = example()
        config["features"]["planning"] = True
        with self.assertRaisesRegex(DemoError, "Planning requires"):
            validate(config)

    def test_planning_with_model_valid(self):
        config = example()
        config["features"].update(planning=True, semantic_model=True)
        validate(config)

    def test_reject_invalid_values(self):
        cases = [
            ("scope", "events", 100000), ("scope", "regions", True),
            ("scope", "months", 0), ("scope", "end_date", "tomorrow"),
            ("deployment", "schema", "dbo]; DROP TABLE x;--"),
            ("features", "app", "yes"), ("customer", "website", "http://example.com"),
            ("customer", "website", "https://user:password@example.com"),
        ]
        for section, key, value in cases:
            with self.subTest(section=section, key=key, value=value):
                config = example()
                config[section][key] = value
                with self.assertRaises(DemoError):
                    validate(config)

    def test_unknown_options_are_errors(self):
        config = example()
        config["scope"]["unlimited"] = True
        with self.assertRaisesRegex(DemoError, "unknown fields"):
            validate(config)

    def test_hash_ignores_dictionary_order(self):
        config = example()
        self.assertEqual(digest(config), digest(dict(reversed(list(config.items())))))


class DataTests(unittest.TestCase):
    def test_both_industries_deterministic(self):
        for scenario in SCENARIOS:
            config = runtime(confirmed(scenario))
            self.assertEqual(build_data(config), build_data(copy.deepcopy(config)))

    def test_seed_changes_events(self):
        a = confirmed()
        b = copy.deepcopy(a)
        b["scope"]["seed"] += 1
        self.assertNotEqual(build_data(runtime(a))[0]["fact_event"],
                            build_data(runtime(b))[0]["fact_event"])

    def test_grains_integrity_and_exact_metrics(self):
        for scenario in SCENARIOS:
            for count in (100, 1200, 10000):
                with self.subTest(scenario=scenario, count=count):
                    config = confirmed(scenario)
                    config["scope"]["events"] = count
                    tables, expected = build_data(runtime(config))
                    self.assertEqual(len(tables), 15)
                    self.assertEqual(len(tables["fact_event"]), count)
                    self.assertEqual(expected["bronze_events"], count + 2)
                    self.assertEqual(expected["duplicates_removed"], 1)
                    self.assertEqual(expected["rejected_events"], 1)
                    ids = [row["event_id"] for row in tables["fact_event"]]
                    self.assertEqual(len(ids), len(set(ids)))
                    for fact, column, dimension in (
                        ("fact_event", "region_id", "dim_region"),
                        ("fact_event", "location_id", "dim_location"),
                        ("fact_event", "resource_id", "dim_resource"),
                        ("fact_event", "reason_id", "dim_reason"),
                        ("fact_finance", "region_id", "dim_region"),
                        ("fact_risk", "region_id", "dim_region"),
                    ):
                        valid = {row[column] for row in tables[dimension]}
                        self.assertTrue(all(row[column] in valid for row in tables[fact]))
                    self.assertEqual(expected["finance_cents"], sum(
                        row["amount_cents"] for row in tables["fact_finance"]))
                    self.assertTrue(all(type(row["amount_cents"]) is int for row in tables["fact_finance"]))
                    self.assertGreater(expected["actionable_events"], 0)
                    self.assertLess(expected["actionable_events"], count)

    def test_date_table_is_contiguous_and_complete(self):
        config = confirmed()
        config["scope"]["end_date"] = "2024-02-29"
        tables, expected = build_data(runtime(config))
        dates = [date.fromisoformat(row["date"]) for row in tables["dim_date"]]
        self.assertTrue(all(b - a == timedelta(days=1) for a, b in zip(dates, dates[1:])))
        self.assertEqual(dates[-1].isoformat(), "2024-02-29")
        self.assertFalse(expected["latest_quarter_is_complete"])
        self.assertTrue(all(date.fromisoformat(row["event_date"]) <= dates[-1]
                            for row in tables["fact_event"]))

    def test_quarter_ranking_and_scope(self):
        tables, expected = build_data(runtime(confirmed()))
        rank = expected["latest_quarter_rank"]
        self.assertEqual(rank, sorted(rank, key=lambda row: (-row["actionable_events"], row["region"])))
        self.assertEqual(sum(row["actionable_events"] for row in rank),
                         expected["latest_quarter_actionable"])
        self.assertTrue(expected["latest_quarter_is_complete"])

    def test_aggregate_view_reconciles_using_sql_engine(self):
        for scenario in SCENARIOS:
            config = confirmed(scenario)
            tables, expected = build_data(runtime(config))
            schema = config["deployment"]["schema"]
            with closing(sqlite3.connect(":memory:")) as sql:
                sql.execute(f"ATTACH DATABASE ':memory:' AS {schema}")
                sql.create_function("YEAR", 1, lambda d: int(d[:4]))
                sql.create_function("DATEPART", 2, lambda part, d: (int(d[5:7]) - 1) // 3 + 1)
                for name, rows in tables.items():
                    columns = list(rows[0])
                    definition = ", ".join(f"[{key}]" for key in columns)
                    sql.execute(f"CREATE TABLE {schema}.{name} ({definition})")
                    slots = ",".join("?" for _ in columns)
                    sql.executemany(f"INSERT INTO {schema}.{name} VALUES ({slots})",
                                    [[row[key] for key in columns] for row in rows])
                query = analytical_sql(config).replace("CREATE OR ALTER VIEW", "CREATE VIEW")
                query = query.replace("COUNT_BIG", "COUNT").replace("DATEPART(quarter,", "DATEPART('quarter',")
                sql.execute(query)
                events, actions, cents = sql.execute(
                    f"SELECT SUM(events),SUM(actionable_events),SUM(amount_cents) "
                    f"FROM {schema}.vw_demo_region_period").fetchone()
                self.assertEqual((events, actions, cents),
                                 (expected["events"], expected["actionable_events"], expected["finance_cents"]))
                year = int(expected["latest_quarter"][:4])
                quarter = int(expected["latest_quarter"][-1])
                actual = sql.execute(
                    f"SELECT SUM(events),SUM(actionable_events),SUM(amount_cents) "
                    f"FROM {schema}.vw_demo_region_period WHERE year=? AND quarter=?",
                    (year, quarter)).fetchone()
                self.assertEqual(actual, (expected["latest_quarter_events"],
                                         expected["latest_quarter_actionable"],
                                         expected["latest_quarter_finance_cents"]))


class RunFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = confirmed()
        generate(self.config, self.root)
        self.state = initialize(self.root, self.config)

    def tearDown(self):
        self.temporary.cleanup()

    def finish(self, gate):
        approve(self.root, gate, "Explicit operator approval")
        complete(self.root, gate, report(read(self.root)[1], gate))


class RunTests(RunFixture):
    def test_no_fabric_calls_during_generation(self):
        with patch.object(Client, "request", side_effect=AssertionError("network")):
            generate(self.config, self.root)
        self.assertTrue((self.root / "notebooks" / "build_demo.ipynb").is_file())

    def test_artifacts_bound_to_approval(self):
        approve(self.root, "story", "Approved")
        (self.root / "scenario.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(DemoError, "artifacts changed"):
            read(self.root)

    def test_configuration_tampering_invalidates(self):
        config = dict(self.config, audience="Changed")
        save(self.root / "config.json", config)
        with self.assertRaisesRegex(DemoError, "artifacts changed"):
            read(self.root)

    def test_prerequisites_cannot_be_skipped(self):
        with self.assertRaisesRegex(DemoError, "prerequisite"):
            approve(self.root, "data-build", "Go")

    def test_unconfirmed_research_blocks_approval(self):
        self.config["research"]["industry_confirmed"] = False
        generate(self.config, self.root)
        initialize(self.root, self.config)
        with self.assertRaisesRegex(DemoError, "unconfirmed"):
            approve(self.root, "story", "Go")

    def test_completion_requires_approval(self):
        with self.assertRaisesRegex(DemoError, "explicitly approved"):
            complete(self.root, "story", report(self.state, "story"))

    def test_completion_requires_all_checks(self):
        approve(self.root, "story", "Go")
        evidence = report(self.state, "story")
        evidence["checks"]["assumptions_reviewed"] = False
        with self.assertRaisesRegex(DemoError, "assumptions_reviewed"):
            complete(self.root, "story", evidence)

    def test_completion_requires_matching_hash(self):
        approve(self.root, "story", "Go")
        evidence = report(self.state, "story")
        evidence["config_hash"] = "wrong"
        with self.assertRaisesRegex(DemoError, "config_hash"):
            complete(self.root, "story", evidence)

    def test_operator_evidence_not_machine_verification(self):
        approve(self.root, "story", "Go")
        evidence = dict(report(self.state, "story"), kind="machine")
        complete(self.root, "story", evidence)
        saved = json.loads((self.root / "evidence" / "story.json").read_text())
        self.assertEqual(saved["kind"], "operator-attestation")
        self.assertEqual(read(self.root)[1]["gates"]["story"]["status"], "complete")

    def test_evidence_tampering_blocks_resume(self):
        self.finish("story")
        (self.root / "evidence" / "story.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(DemoError, "Evidence changed"):
            read(self.root)

    def test_data_completion_cannot_be_attested(self):
        self.finish("story")
        self.finish("design")
        approve(self.root, "data-build", "Go")
        with self.assertRaisesRegex(DemoError, "durable notebook"):
            complete(self.root, "data-build", {})

    def test_disabled_gates_rejected(self):
        with self.assertRaisesRegex(DemoError, "not enabled"):
            approve(self.root, "planning", "Go")

    def test_optional_gate_order(self):
        self.config["features"].update(semantic_model=True, planning=True)
        generate(self.config, self.root)
        state = initialize(self.root, self.config)
        self.assertEqual(list(state["gates"]),
                         ["story", "design", "data-build", "fabric-iq",
                          "semantic-model", "planning", "app", "rehearsal"])

    def test_concurrent_commands_blocked(self):
        with locked(self.root):
            with self.assertRaisesRegex(DemoError, "locked"):
                with locked(self.root):
                    pass
        self.assertFalse((self.root / ".run.lock").exists())

    def test_notebook_compiles_and_generator_matches(self):
        nb = notebook(self.config)
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                ast.parse("".join(cell["source"]))
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])
                self.assertTrue(all(line.endswith("\n") for line in cell["source"][:-1]))
        setup = "".join(nb["cells"][1]["source"])
        # Execute portable embedded generator, without pretending to execute Spark.
        setup = setup.replace("from pyspark.sql import functions as F, types as T\n", "")
        namespace = {}
        exec(compile(setup, "<generated-notebook-setup>", "exec"), namespace)
        self.assertEqual(namespace["tables"], build_data(runtime(self.config))[0])

    def test_semantic_model_does_not_have_ambiguous_region_path(self):
        model = semantic_contract(self.config)
        self.assertFalse(any(row[0] == "dim_location" for row in model["relationships"]))
        self.assertIn("DIVIDE", model["measures"]["Financial Amount"])

    @unittest.skipUnless(importlib.util.find_spec("nbformat"), "Install .[dev] for official notebook schema checks")
    def test_notebook_matches_official_jupyter_schema(self):
        import nbformat
        for scenario in SCENARIOS:
            nbformat.validate(nbformat.from_dict(notebook(confirmed(scenario))))


class FakeFabric:
    def __init__(self):
        self.items = [{"id": "lakehouse", "displayName": "lh_demo", "type": "Lakehouse"}]
        self.jobs = []
        self.posts = []
        self.status = "InProgress"
        self.lose_submission = False

    def listing(self, path):
        if path == "/v1/workspaces":
            return [{"id": "workspace", "displayName": "Approved demo workspace", "capacityId": "capacity"}]
        if path == "/v1/capacities":
            return [{"id": "capacity", "state": "Active"}]
        if path.endswith("/items"):
            return self.items
        if path.endswith("/jobs/instances"):
            return self.jobs
        raise AssertionError(path)

    def request(self, method, path, body=None):
        if method == "POST":
            self.posts.append((path, body))
            if path.endswith("/items"):
                item = {"id": "notebook", "displayName": body["displayName"], "type": body["type"]}
                self.items.append(item)
                return 201, {}, item
            if "jobType=RunNotebook" in path:
                self.jobs = [{"id": "job", "status": self.status}]
                if self.lose_submission:
                    raise DemoError("Lost submit response")
                return 202, {"Location": "/v1/workspaces/workspace/items/notebook/jobs/instances/job"}, {}
        if method == "GET" and path.endswith("/job"):
            return 200, {}, {"id": "job", "status": self.status}
        raise AssertionError((method, path))


class DeploymentTests(RunFixture):
    def ready(self):
        self.finish("story")
        self.finish("design")
        approve(self.root, "data-build", "Approved workspace and fresh schema")

    def test_deploy_without_approval_never_contacts_fabric(self):
        fake = FakeFabric()
        with self.assertRaises(DemoError):
            deploy_data(self.root, 0, fake)
        self.assertEqual(fake.posts, [])

    def test_timeout_and_resume_does_not_resubmit(self):
        self.ready()
        fake = FakeFabric()
        with self.assertRaisesRegex(DemoError, "Local monitoring stopped"):
            deploy_data(self.root, 0, fake)
        self.assertEqual(read(self.root)[1]["resources"]["job_id"], "job")
        fake.status = "Completed"
        self.assertEqual(deploy_data(self.root, 0, fake)["status"], "Completed")
        self.assertEqual(len(fake.posts), 2)
        self.assertEqual(deploy_data(self.root, 0, fake)["status"], "already-complete")
        self.assertEqual(len(fake.posts), 2)
        payload = fake.posts[0][1]
        import base64
        nb = json.loads(base64.b64decode(payload["definition"]["parts"][0]["payload"]))
        self.assertEqual(nb["metadata"]["dependencies"]["lakehouse"]["default_lakehouse"], "lakehouse")

    def test_lost_submit_response_resumes_by_discovery(self):
        self.ready()
        fake = FakeFabric()
        fake.lose_submission = True
        with self.assertRaisesRegex(DemoError, "Lost submit"):
            deploy_data(self.root, 0, fake)
        fake.lose_submission = False
        fake.status = "Completed"
        self.assertEqual(deploy_data(self.root, 0, fake)["status"], "Completed")
        self.assertEqual(len(fake.posts), 2)

    def test_ambiguous_submit_never_reposts(self):
        self.ready()
        fake = FakeFabric()
        fake.lose_submission = True
        with self.assertRaises(DemoError):
            deploy_data(self.root, 0, fake)
        fake.jobs = []
        with self.assertRaisesRegex(DemoError, "ambiguous"):
            deploy_data(self.root, 0, fake)
        self.assertEqual(len(fake.posts), 2)

    def test_failed_job_cannot_be_silently_retried(self):
        self.ready()
        fake = FakeFabric()
        fake.status = "Failed"
        for _ in range(2):
            with self.assertRaisesRegex(DemoError, "Notebook Failed"):
                deploy_data(self.root, 0, fake)
        self.assertEqual(len(fake.posts), 2)

    def test_duplicate_names_block_creation(self):
        fake = FakeFabric()
        fake.items.append(dict(fake.items[0]))
        self.ready()
        with self.assertRaisesRegex(DemoError, "Multiple"):
            deploy_data(self.root, 0, fake)
        self.assertEqual(fake.posts, [])

    def test_inactive_capacity_blocks_writes(self):
        fake = FakeFabric()
        original = fake.listing
        fake.listing = lambda path: [{"id": "capacity", "state": "Paused"}] if path == "/v1/capacities" else original(path)
        with self.assertRaisesRegex(DemoError, "Active"):
            preflight(self.config, fake)
        self.assertEqual(fake.posts, [])

    def test_untrusted_api_url_rejected_before_auth(self):
        with patch("shutil.which", side_effect=AssertionError("must not authenticate")):
            for url in ("https://attacker.example", "http://api.fabric.microsoft.com",
                        "https://api.fabric.microsoft.com@attacker.example"):
                with self.assertRaisesRegex(DemoError, "outside"):
                    Client().request("GET", url)

    def test_ambiguous_create_does_not_repeat_post(self):
        fake = FakeFabric()
        state = read(self.root)[1]
        state["resources"]["notebook_attempted"] = "earlier"
        with self.assertRaisesRegex(DemoError, "ambiguous"):
            ensure_item(fake, self.root, state, "workspace", "Notebook", "missing", {}, 0)
        self.assertEqual(fake.posts, [])

    def test_incomplete_operation_is_polled_before_item_reuse(self):
        fake = FakeFabric()
        state = read(self.root)[1]
        state["resources"]["lakehouse_operation"] = "/v1/operations/existing"
        with patch("demo_accelerator.fabric.poll_operation", side_effect=DemoError("Still running")):
            with self.assertRaisesRegex(DemoError, "Still running"):
                ensure_item(fake, self.root, state, "workspace", "Lakehouse", "lh_demo", {}, 0)
        self.assertEqual(fake.posts, [])

    def test_paginated_lists_and_continuation_token(self):
        client = Client()
        with patch.object(client, "request", side_effect=[
            (200, {}, {"value": [{"id": "a"}], "continuationToken": "token+/="}),
            (200, {}, {"value": [{"id": "b"}]}),
        ]) as request:
            self.assertEqual(client.listing("/v1/items?type=Lakehouse"), [{"id": "a"}, {"id": "b"}])
        self.assertIn("continuationToken=token%2B%2F%3D", request.call_args_list[1].args[1])


if __name__ == "__main__":
    unittest.main()
