import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from demo_accelerator.artifacts import (
    analytical_sql, generate, notebook, ontology_contract, scenario_contract, semantic_contract,
)
from demo_accelerator.cli import execute, parser
from demo_accelerator.config import DemoError, brief, digest, validate
from demo_accelerator.existing_data import (
    evidence_fields, inspect_shortcuts, setup_lakehouse,
)
from demo_accelerator.fabric import Client, deploy_data
from demo_accelerator.state import REQUIRED_CHECKS, approve, complete, initialize, read


WORKSPACE = "10000000-0000-0000-0000-000000000001"
LAKEHOUSE = "20000000-0000-0000-0000-000000000002"
SOURCE = "30000000-0000-0000-0000-000000000003"


def intake():
    config = brief("existing-lakehouse")
    config["existing_data"]["tables"] = [{"name": "orders", "purpose": "Order fulfillment analysis"}]
    config["research"] = {"industry_confirmed": True, "notes": "Public context reviewed",
                          "references": ["https://example.com"]}
    return config


class FakeExistingFabric:
    def __init__(self):
        self.items = []
        self.posts = []
        self.shortcuts = [{
            "path": "Tables/demo_customer", "name": "orders",
            "target": {"type": "OneLake", "oneLake": {
                "workspaceId": WORKSPACE, "itemId": SOURCE, "path": "Tables/sales/orders"}},
        }]
        self.lose_create = False
        self.async_create = False
        self.operation_status = "Running"

    def listing(self, path):
        if path == "/v1/workspaces":
            return [{"id": WORKSPACE, "displayName": "CHOOSE_AN_APPROVED_WORKSPACE", "capacityId": "c"}]
        if path == "/v1/capacities":
            return [{"id": "c", "state": "Active"}]
        if path.endswith("/items"):
            return self.items
        if path.endswith("/shortcuts"):
            return self.shortcuts
        raise AssertionError(path)

    def request(self, method, path, body=None):
        if method == "POST" and path.endswith("/items"):
            self.posts.append((path, body))
            item = {"id": LAKEHOUSE, "displayName": body["displayName"], "type": body["type"]}
            if self.lose_create:
                raise DemoError("Create outcome unavailable")
            self.items.append(item)
            if self.async_create:
                return 202, {"Location": "/v1/operations/create-lakehouse"}, {}
            return 201, {}, item
        if method == "GET" and path == "/v1/operations/create-lakehouse":
            return 200, {}, {"status": self.operation_status}
        raise AssertionError((method, path, body))


class ExistingContractTests(unittest.TestCase):
    def test_synthetic_default_validation_does_not_change_config_or_digest(self):
        config = brief()
        before = copy.deepcopy(config)
        original_hash = digest(config)
        validate(config)
        self.assertEqual(config, before)
        self.assertEqual(digest(config), original_hash)
        self.assertNotIn("data_mode", config)
        explicit = dict(config, data_mode="synthetic")
        validate(explicit)

    def test_existing_brief_and_scope(self):
        config = intake()
        self.assertIs(validate(config), config)
        for key, value in (("max_query_seconds", 301), ("max_result_rows", True),
                           ("baseline_max_age_hours", 0), ("seed", 42)):
            with self.subTest(key=key):
                invalid = copy.deepcopy(config)
                invalid["scope"][key] = value
                with self.assertRaises(DemoError):
                    validate(invalid)

    def test_existing_table_count_is_not_arbitrarily_capped(self):
        config = intake()
        config["existing_data"]["tables"] = [
            {"name": f"table_{i}", "purpose": "Operator-selected analytical table"}
            for i in range(25)
        ]
        validate(config)
        self.assertEqual(len(config["existing_data"]["tables"]), 25)

    def test_rejects_mixed_paths_unknown_fields_and_unsafe_aliases(self):
        for section, key, value in (
            (None, "proposal", {}), (None, "data_mode", "auto"),
            ("existing_data", "allow_writes", True),
        ):
            config = intake()
            (config if section is None else config[section])[key] = value
            with self.assertRaises(DemoError):
                validate(config)
        for name in ("dbo.orders", "Orders", "../orders", "a]; DROP TABLE x", ""):
            config = intake()
            config["existing_data"]["tables"][0]["name"] = name
            with self.assertRaises(DemoError):
                validate(config)
        config = intake()
        config["existing_data"]["tables"] *= 2
        with self.assertRaisesRegex(DemoError, "Duplicate"):
            validate(config)

    def test_cli_init_plan_and_generate_without_network_or_synthetic_build(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            Client, "request", side_effect=AssertionError("network")
        ), patch("demo_accelerator.flexible_data.build_blueprint", side_effect=AssertionError("synthetic")):
            root = Path(temporary)
            config_path, run = root / "intake.json", root / "run"
            execute(parser().parse_args(["init", "--data-mode", "existing-lakehouse",
                                         "--output", str(config_path)]))
            self.assertIn("discovery", execute(parser().parse_args(["plan", str(config_path)])))
            with self.assertRaisesRegex(DemoError, "Select table"):
                execute(parser().parse_args(["generate", str(config_path), "--run-dir", str(run)]))
            self.assertFalse(run.exists())
            config_path.write_text(json.dumps(intake()), encoding="utf-8")
            result = execute(parser().parse_args(["generate", str(config_path), "--run-dir", str(run)]))
            self.assertFalse(result["expected"]["synthetic_data_generated"])
            self.assertFalse(json.loads((run / "scenario.json").read_text())["synthetic"])
            self.assertFalse((run / "notebooks").exists())
            self.assertFalse((run / "expected.json").exists())
            sql = (run / "assessment-metadata.sql").read_text()
            self.assertIn("INFORMATION_SCHEMA.COLUMNS", sql)
            self.assertNotIn("SELECT *", sql)
            self.assertNotIn("CREATE ", sql)
            guide = (run / "OPERATOR.md").read_text()
            for requirement in ("NOT inherently read-only", "inspect-shortcuts", "No SELECT *",
                                "No synthetic notebook", "separately approved"):
                self.assertIn(requirement, guide)

    def test_legacy_init_and_existing_mode_are_incompatible(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "intake.json"
            with self.assertRaisesRegex(DemoError, "Legacy"):
                execute(parser().parse_args(["init", "--scenario", "healthcare-access",
                                             "--data-mode", "existing-lakehouse", "--output", str(path)]))
            self.assertFalse(path.exists())

    def test_synthetic_artifact_helpers_refuse_existing_data(self):
        for build in (notebook, analytical_sql, ontology_contract, scenario_contract, semantic_contract):
            with self.subTest(build=build.__name__), self.assertRaisesRegex(DemoError, "assessed mappings"):
                build(intake())

    def test_specialist_client_uses_owning_header(self):
        client = Client(skill="onelake-catalog-cli")
        response = MagicMock(status=200, headers={})
        response.read.return_value = b"{}"
        response.__enter__.return_value = response
        with patch("shutil.which", return_value="az"), patch(
            "subprocess.run", return_value=MagicMock(returncode=0, stdout="test-token")
        ), patch.object(client.opener, "open", return_value=response) as call:
            client.request("GET", "/v1/workspaces")
        request = call.call_args.args[0]
        self.assertEqual(dict(request.header_items())["X-ms-fabric-skill"], "onelake-catalog-cli")


class ExistingRunTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = intake()
        generate(self.config, self.root)
        initialize(self.root, self.config)
        self.client = FakeExistingFabric()

    def tearDown(self):
        self.temporary.cleanup()

    def setup_lakehouse(self):
        approve(self.root, "lakehouse-setup", "Explicit creation permission")
        return setup_lakehouse(self.root, 0, self.client)

    def shortcuts_report(self):
        self.setup_lakehouse()
        approve(self.root, "shortcuts", "Manual shortcut and target permission checkpoint")
        inventory = inspect_shortcuts(self.root, self.client)
        report = self.report("shortcuts")
        report["inventory_sha256"] = inventory["inventory_sha256"]
        for binding, observed in zip(report["bindings"], inventory["bindings"]):
            binding.update(target=observed["target"], read_only_verified=True,
                           source_reference="Owner-approved source table",
                           permission_reference="Effective source permissions reviewed without writes")
        return report

    def readiness_report(self):
        complete(self.root, "shortcuts", self.shortcuts_report())
        approve(self.root, "data-readiness", "Allowlisted metadata and aggregate read scope approved")
        report = self.report("data-readiness")
        assessment = report["assessment"]
        assessment.update(observed_at=datetime.now(timezone.utc).isoformat(),
                          business_question="What is the complete-period order volume?",
                          sensitivity_and_disclosure="Aggregate-only disclosure approved",
                          scan_budget="One selected partition, maximum 60 seconds and 100 result rows",
                          drift_policy="Reconcile source versions and repeat aggregate before publication")
        assessment["tables"][0].update(
            columns_and_types="order_id int64, order_date date", grain="One row per order",
            key_findings="No null or duplicate order_id in approved period",
            relationship_findings="No joins needed; no inferred relationship",
            date_coverage_and_roles="Complete period, order_date role",
            limitations="No point-in-time guarantee beyond observed source version")
        assessment["metrics"][0].update(
            name="order_count", definition="Count orders; no allocation", unit="orders",
            grain_and_filters="Selected complete calendar month", baseline_value=10,
            query_reference="Private approved COUNT_BIG query and timestamped aggregate receipt")
        return report

    def report(self, gate):
        _, state = read(self.root)
        return {
            "config_hash": state["config_hash"], "notes": "Owner-attested test evidence",
            "references": ["private-verification-reference"],
            "checks": dict.fromkeys(REQUIRED_CHECKS[gate], True),
            **evidence_fields(self.config, gate),
            "destination": {"workspace_id": WORKSPACE, "lakehouse_id": LAKEHOUSE},
        }

    def test_gate_order_and_machine_only_setup(self):
        self.assertEqual(list(read(self.root)[1]["gates"])[:6],
                         ["lakehouse-setup", "shortcuts", "data-readiness", "story", "design", "fabric-iq"])
        with self.assertRaisesRegex(DemoError, "prerequisite"):
            approve(self.root, "data-readiness", "Not allowed yet")
        approve(self.root, "lakehouse-setup", "Create approved")
        with self.assertRaisesRegex(DemoError, "deployment command"):
            complete(self.root, "lakehouse-setup", {})

    def test_missing_research_blocks_setup_approval_before_any_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = intake()
            config["research"]["notes"] = ""
            root = Path(temporary)
            generate(config, root)
            initialize(root, config)
            with self.assertRaisesRegex(DemoError, "research notes"):
                approve(root, "lakehouse-setup", "Cannot create an unusable immutable run")
            with self.assertRaises(DemoError):
                setup_lakehouse(root, 0, self.client)
            self.assertEqual(self.client.posts, [])

    def test_unapproved_or_wrong_mode_commands_cannot_contact_fabric(self):
        with self.assertRaises(DemoError):
            setup_lakehouse(self.root, 0, self.client)
        with self.assertRaises(DemoError):
            inspect_shortcuts(self.root, self.client)
        with self.assertRaisesRegex(DemoError, "prohibited"):
            deploy_data(self.root, 0, self.client)
        self.assertEqual(self.client.posts, [])

    def test_synthetic_run_rejects_existing_only_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = json.loads(
                (Path(__file__).resolve().parents[1] / "examples" / "insurance-claims.json").read_text()
            )
            root = Path(temporary)
            generate(config, root)
            initialize(root, config)
            for command in (setup_lakehouse, inspect_shortcuts):
                with self.assertRaisesRegex(DemoError, "requires existing-lakehouse"):
                    command(root, client=self.client)
            self.assertEqual(self.client.posts, [])

    def test_cli_templates_keep_permission_and_readiness_checks_false(self):
        self.setup_lakehouse()
        for gate in ("shortcuts", "data-readiness"):
            result = execute(parser().parse_args(["evidence-template", "--run-dir", str(self.root),
                                                 "--gate", gate]))
            self.assertFalse(any(result["checks"].values()))
            self.assertEqual(result["destination"]["lakehouse_id"], LAKEHOUSE)
        self.assertFalse(result["assessment"]["observed_at"])

    def test_creates_only_lakehouse_then_stops_and_resume_is_idempotent(self):
        result = self.setup_lakehouse()
        self.assertEqual(result["status"], "awaiting-manual-shortcuts")
        self.assertEqual(len(self.client.posts), 1)
        self.assertEqual(self.client.posts[0][1], {
            "displayName": self.config["deployment"]["lakehouse_name"], "type": "Lakehouse",
            "creationPayload": {"enableSchemas": True},
        })
        setup_lakehouse(self.root, 0, self.client)
        self.assertEqual(len(self.client.posts), 1)
        self.assertEqual(read(self.root)[1]["gates"]["shortcuts"]["status"], "pending")
        self.client.items = []
        with self.assertRaisesRegex(DemoError, "missing"):
            setup_lakehouse(self.root, 0, self.client)
        self.assertEqual(len(self.client.posts), 1)

    def test_preexisting_lakehouse_rejected(self):
        self.client.items = [{"id": LAKEHOUSE, "type": "Lakehouse",
                              "displayName": self.config["deployment"]["lakehouse_name"]}]
        with self.assertRaisesRegex(DemoError, "without this run"):
            self.setup_lakehouse()
        self.assertEqual(self.client.posts, [])

    def test_ambiguous_create_never_reposts(self):
        self.client.lose_create = True
        with self.assertRaisesRegex(DemoError, "outcome"):
            self.setup_lakehouse()
        with self.assertRaisesRegex(DemoError, "ambiguous"):
            setup_lakehouse(self.root, 0, self.client)
        self.assertEqual(len(self.client.posts), 1)

    def test_async_create_timeout_resumes_existing_operation(self):
        self.client.async_create = True
        with self.assertRaisesRegex(DemoError, "deadline"):
            self.setup_lakehouse()
        state = read(self.root)[1]
        self.assertIn("lakehouse_operation", state["resources"])
        self.client.operation_status = "Succeeded"
        setup_lakehouse(self.root, 0, self.client)
        self.assertEqual(len(self.client.posts), 1)
        self.assertNotIn("lakehouse_operation", read(self.root)[1]["resources"])

    def test_shortcut_inventory_rejects_out_of_scope_and_external_targets(self):
        self.setup_lakehouse()
        approve(self.root, "shortcuts", "Review")
        original = copy.deepcopy(self.client.shortcuts)
        cases = [
            [], original * 2,
            [dict(original[0], path="Tables")],
            [dict(original[0], name="unapproved")],
            [dict(original[0], target={"type": "AmazonS3"})],
            [dict(original[0], target={"oneLake": {"workspaceId": WORKSPACE,
                                                 "itemId": SOURCE, "path": "Tables"}})],
            [dict(original[0], target={"oneLake": {"workspaceId": WORKSPACE,
                                                 "itemId": LAKEHOUSE, "path": "Tables/demo_customer/orders"}})],
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                self.client.shortcuts = rows
                with self.assertRaises(DemoError):
                    inspect_shortcuts(self.root, self.client)
        self.assertEqual(len(self.client.posts), 1)

    def test_shortcut_inventory_accepts_one_optional_leading_path_slash(self):
        self.setup_lakehouse()
        approve(self.root, "shortcuts", "Review")
        for path in ("Tables/demo_customer", "/Tables/demo_customer"):
            self.client.shortcuts[0]["path"] = path
            result = inspect_shortcuts(self.root, self.client)
            self.assertEqual(result["bindings"][0]["table"], "orders")
        for path in ("//Tables/demo_customer", "/Tables/demo_customer/",
                     "/Tables/other", "/Tables/demo_customer/../demo_customer"):
            self.client.shortcuts[0]["path"] = path
            with self.assertRaisesRegex(DemoError, "unapproved paths"):
                inspect_shortcuts(self.root, self.client)

    def test_shortcuts_require_matching_inventory_and_read_only_evidence(self):
        report = self.shortcuts_report()
        for edit in (
            lambda r: r.update(inventory_sha256="wrong"),
            lambda r: r["bindings"][0].update(read_only_verified=False),
            lambda r: r["bindings"][0].update(permission_reference=""),
            lambda r: r["bindings"][0].update(target={"path": "changed"}),
            lambda r: r["bindings"][0].update(table=[]),
            lambda r: r["destination"].update(lakehouse_id=SOURCE),
        ):
            invalid = copy.deepcopy(report)
            edit(invalid)
            with self.assertRaises(DemoError):
                complete(self.root, "shortcuts", invalid)
        complete(self.root, "shortcuts", report)
        state = read(self.root)[1]
        self.assertEqual(state["gates"]["shortcuts"]["status"], "complete")
        with self.assertRaises(DemoError):
            inspect_shortcuts(self.root, self.client)
        evidence = json.loads((self.root / state["gates"]["shortcuts"]["evidence"]).read_text())
        self.assertEqual(evidence["kind"], "operator-attestation")

    def test_inventory_evidence_is_tamper_checked(self):
        self.shortcuts_report()
        state = read(self.root)[1]
        (self.root / state["resources"]["shortcut_inventory"]["evidence"]).write_text("{}")
        with self.assertRaisesRegex(DemoError, "inventory evidence changed"):
            read(self.root)

    def test_readiness_rejects_missing_grains_stale_baseline_and_record_samples(self):
        report = self.readiness_report()
        for edit in (
            lambda r: r["assessment"].update(observed_at=None),
            lambda r: r["assessment"].update(
                observed_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat()),
            lambda r: r["assessment"].update(
                observed_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat()),
            lambda r: r["assessment"].update(observed_at="2026-01-01T00:00:00"),
            lambda r: r["assessment"].update(
                observed_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()),
            lambda r: r["assessment"]["tables"][0].update(grain=""),
            lambda r: r["assessment"]["tables"][0].update(name=[]),
            lambda r: r["assessment"]["tables"][0].update(records=[{"order_id": 1}]),
            lambda r: r["assessment"].update(scan_budget=""),
            lambda r: r["assessment"].update(metrics=[]),
            lambda r: r["assessment"]["metrics"][0].update(baseline_value=[{"order_id": 1}]),
            lambda r: r["assessment"]["metrics"][0].update(baseline_value=float("nan")),
        ):
            invalid = copy.deepcopy(report)
            edit(invalid)
            with self.assertRaises(DemoError):
                complete(self.root, "data-readiness", invalid)
        complete(self.root, "data-readiness", report)
        approve(self.root, "story", "Approve assessed story and research")
        complete(self.root, "story", self.report("story"))
        approve(self.root, "design", "Approve assessed model and limits")
        complete(self.root, "design", self.report("design"))
        approve(self.root, "fabric-iq", "Proceed using assessed mappings")
        self.assertEqual(len(self.client.posts), 1)


if __name__ == "__main__":
    unittest.main()
