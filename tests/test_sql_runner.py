import copy
import json
import sqlite3
import struct
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from demo_accelerator.artifacts import generate
from demo_accelerator.cli import execute, parser
from demo_accelerator.config import DemoError, digest
from demo_accelerator.existing_data import evidence_fields, inspect_shortcuts, setup_lakehouse
from demo_accelerator.sql_runner import (
    IDENTITY_SQL, OdbcSession, aggregate_sql, approve_plan, preview, quote,
    relationship_sql, run, scalar,
)
from demo_accelerator.state import REQUIRED_CHECKS, approve, complete, initialize, read
from test_existing_data import FakeExistingFabric, LAKEHOUSE, WORKSPACE, intake


LOGIN = "reader@example.test"


class Session:
    def __init__(self, server, database, timeout):
        self.timeout, self.database = timeout, database
        self.calls, self.closed = [], False
        self.login = LOGIN
        self.fail_aggregate = False

    def query(self, sql, parameters, limit):
        self.calls.append((sql, parameters, limit))
        if sql == IDENTITY_SQL:
            return [{"execution_login": self.login, "database_user": self.login,
                     "database_name": self.database}]
        if "INFORMATION_SCHEMA.COLUMNS" in sql:
            return [{"COLUMN_NAME": "Amount", "DATA_TYPE": "decimal", "IS_NULLABLE": "YES",
                     "ORDINAL_POSITION": 1},
                    {"COLUMN_NAME": "Order Date", "DATA_TYPE": "date", "IS_NULLABLE": "NO",
                     "ORDINAL_POSITION": 2}]
        if self.fail_aggregate:
            raise DemoError("SQL statement failed or timed out")
        return [{"total": "10.25"}]

    def close(self):
        self.closed = True


class SqlRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = intake()
        generate(self.config, self.root)
        initialize(self.root, self.config)
        self.fabric = FakeExistingFabric()
        approve(self.root, "lakehouse-setup", "Explicit creation approval")
        setup_lakehouse(self.root, 0, self.fabric)
        approve(self.root, "shortcuts", "Inventory and read-only review approved")
        inventory = inspect_shortcuts(self.root, self.fabric)
        report = {
            "config_hash": digest(self.config), "notes": "Owner attests read-only caller execution",
            "references": ["owner-permission-review"],
            "checks": dict.fromkeys(REQUIRED_CHECKS["shortcuts"], True),
            **evidence_fields(self.config, "shortcuts"),
            "inventory_sha256": inventory["inventory_sha256"],
            "destination": {"workspace_id": WORKSPACE, "lakehouse_id": LAKEHOUSE},
        }
        for binding, observed in zip(report["bindings"], inventory["bindings"]):
            binding.update(target=observed["target"], read_only_verified=True,
                           source_reference="inventory", permission_reference="owner-review")
        complete(self.root, "shortcuts", report)
        self.plan = {
            "version": 1, "config_hash": digest(self.config),
            "inventory_sha256": inventory["inventory_sha256"], "expected_login": LOGIN,
            "queries": [{"id": "order_columns", "kind": "columns", "table": "orders",
                         "scan_budget": "Catalog only; one approved table",
                         "disclosure": "Column metadata approved"}],
        }
        self.client = MagicMock()
        self.client.request.return_value = (200, {}, {
            "id": LAKEHOUSE, "displayName": self.config["deployment"]["lakehouse_name"],
            "properties": {"sqlEndpointProperties": {
                "id": "endpoint", "provisioningStatus": "Success",
                "connectionString": "example.datawarehouse.fabric.microsoft.com",
            }},
        })
        self.sessions = []

    def tearDown(self):
        self.temporary.cleanup()

    def factory(self, server, database, timeout):
        session = Session(server, database, timeout)
        self.sessions.append(session)
        return session

    def execute(self, plan=None, factory=None):
        return run(self.root, expected_login=LOGIN, plan=plan, client=self.client,
                   inventory_client=self.fabric, session_factory=factory or self.factory)

    def authorize(self):
        approve(self.root, "data-readiness", "Metadata and reviewed aggregate scope")
        return approve_plan(self.root, self.plan, "Approved exact plan, scan and disclosure budgets")

    def aggregate(self):
        self.plan["queries"] = [{
            "id": "order_total", "kind": "aggregate", "table": "orders",
            "scan_budget": "One approved day; timeout 60 seconds; one output row",
            "disclosure": "Sample monetary aggregate approved",
            "measures": [{"name": "total", "function": "sum", "column": "Amount"}],
            "filters": [{"column": "Order Date", "op": ">=", "value": "2016-01-01"},
                        {"column": "Order Date", "op": "<", "value": "2016-01-02"}],
        }]

    def test_identity_only_preflight_preserves_gates_and_immutable_manifest(self):
        result = self.execute()
        session = self.sessions[0]
        self.assertEqual([call[0] for call in session.calls], [IDENTITY_SQL])
        self.assertEqual(session.timeout, 60)
        self.assertTrue(session.closed)
        self.assertTrue(result["identity_only"])
        self.assertEqual(read(self.root)[1]["gates"]["data-readiness"]["status"], "pending")

    def test_gates_and_exact_plan_approval_required_before_connections(self):
        with self.assertRaisesRegex(DemoError, "approved"):
            self.execute(self.plan)
        with self.assertRaisesRegex(DemoError, "approved"):
            approve_plan(self.root, self.plan, "Cannot approve before gate")
        approve(self.root, "data-readiness", "Approved metadata scope")
        with self.assertRaisesRegex(DemoError, "exact SQL plan"):
            self.execute(self.plan)
        self.assertFalse(self.sessions)

    def test_metadata_execution_with_hash_bound_approval(self):
        self.authorize()
        result = self.execute(self.plan)
        receipt = json.loads((self.root / result["evidence"]).read_text())
        self.assertEqual(receipt["status"], "succeeded")
        self.assertEqual(receipt["queries"][0]["rows"][1]["COLUMN_NAME"], "Order Date")
        self.assertEqual(receipt["plan_sha256"], digest(self.plan))
        self.assertEqual(read(self.root)[1]["gates"]["data-readiness"]["status"], "approved")
        self.plan["queries"][0]["disclosure"] = "Changed"
        with self.assertRaisesRegex(DemoError, "exact SQL plan"):
            self.execute(self.plan)

    def test_rejects_tampered_approval_evidence(self):
        approved = self.authorize()
        (self.root / approved["evidence"]).write_text("{}")
        with self.assertRaisesRegex(DemoError, "approval evidence changed"):
            self.execute(self.plan)

    def test_cli_wires_preflight_preview_approval_and_execution(self):
        preflight = parser().parse_args([
            "sql-preflight", "--run-dir", str(self.root), "--expected-login", LOGIN])
        with patch("demo_accelerator.sql_runner.run", return_value={"identity_only": True}) as call:
            self.assertTrue(execute(preflight)["identity_only"])
            call.assert_called_once_with(self.root, expected_login=LOGIN)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "plan.json"
            path.write_text(json.dumps(self.plan), encoding="utf-8")
            args = ["--run-dir", str(self.root), "--plan", str(path)]
            self.assertEqual(execute(parser().parse_args(["sql-plan", *args]))["plan_sha256"],
                             digest(self.plan))
            approve(self.root, "data-readiness", "Metadata only")
            self.assertEqual(execute(parser().parse_args([
                "approve-sql-plan", *args, "--note", "Exact metadata plan approved"]))["status"],
                "approved")
            with patch("demo_accelerator.sql_runner.run", return_value={"status": "succeeded"}) as call:
                self.assertEqual(execute(parser().parse_args(["run-sql-plan", *args]))["status"],
                                 "succeeded")
                call.assert_called_once_with(self.root, plan=self.plan)

    def test_identity_mismatch_stops_before_catalog_queries(self):
        def wrong(server, database, timeout):
            session = self.factory(server, database, timeout)
            session.login = "writer@example.test"
            return session
        with self.assertRaisesRegex(DemoError, "identity/database mismatch"):
            self.execute(factory=wrong)
        self.assertEqual(len(self.sessions[0].calls), 1)
        self.assertTrue(self.sessions[0].closed)
        receipt = json.loads(next((self.root / "evidence").glob("sql-execution-*")).read_text())
        self.assertEqual(receipt["status"], "failed-remote-status-unconfirmed")

    def test_aggregate_is_parameterized_single_table_and_reads_metadata_first(self):
        self.aggregate()
        self.plan["queries"][0]["filters"][0]["value"] = "x'; DROP TABLE orders;--"
        self.authorize()
        self.execute(self.plan)
        sql, parameters, limit = self.sessions[0].calls[-1]
        self.assertIn("SUM([Amount])", sql)
        self.assertIn("[demo_customer].[orders]", sql)
        self.assertNotIn("DROP", sql)
        self.assertIn("DROP", parameters[0])
        self.assertEqual(limit, 100)
        self.assertIn("INFORMATION_SCHEMA", self.sessions[0].calls[-2][0])

    def test_timeout_receipt_is_persisted_without_retry_or_gate_completion(self):
        self.aggregate()
        self.authorize()
        def failing(server, database, timeout):
            session = self.factory(server, database, timeout)
            session.fail_aggregate = True
            return session
        with self.assertRaisesRegex(DemoError, "timed out"):
            self.execute(self.plan, failing)
        self.assertEqual(len(self.sessions), 1)
        self.assertTrue(self.sessions[0].closed)
        receipt = json.loads(next((self.root / "evidence").glob("sql-execution-*")).read_text())
        self.assertEqual(receipt["queries"][0]["status"], "started")
        self.assertNotIn("rows", receipt["queries"][0])
        self.assertEqual(receipt["status"], "failed-remote-status-unconfirmed")
        self.assertEqual(read(self.root)[1]["gates"]["data-readiness"]["status"], "approved")

    def test_shortcut_drift_blocks_before_connection(self):
        self.authorize()
        self.fabric.shortcuts[0]["target"]["oneLake"]["path"] = "Tables/other/orders"
        with self.assertRaisesRegex(DemoError, "drifted"):
            self.execute(self.plan)
        self.assertFalse(self.sessions)

    def test_untrusted_or_changed_endpoint_blocks_token_use(self):
        item = self.client.request.return_value[2]
        item["properties"]["sqlEndpointProperties"]["connectionString"] = "evil.example;UID=bad"
        with self.assertRaisesRegex(DemoError, "validated Fabric SQL host"):
            self.execute()
        self.assertFalse(self.sessions)
        item["displayName"] = "different"
        with self.assertRaisesRegex(DemoError, "identity differs"):
            self.execute()

    def test_plan_rejects_arbitrary_sql_raw_rows_and_unapproved_scope(self):
        for update in ({"sql": "DROP TABLE orders"}, {"kind": "select"},
                       {"table": "other"}, {"kind": "columns", "filters": [{}]},
                       {"disclosure": ""}, {"scan_budget": ""}):
            plan = copy.deepcopy(self.plan)
            plan["queries"][0].update(update)
            with self.subTest(update=update), self.assertRaises(DemoError):
                preview(self.root, plan)
        self.aggregate()
        for function in ("EXEC", "sum(amount); DROP", "raw", []):
            plan = copy.deepcopy(self.plan)
            plan["queries"][0]["measures"][0]["function"] = function
            with self.assertRaises(DemoError):
                preview(self.root, plan)

    def test_quoted_columns_types_and_exact_decimals(self):
        self.assertEqual(quote("odd]column"), "[odd]]column]")
        self.assertEqual(scalar(Decimal("123.4500")), "123.4500")
        for value in (float("nan"), Decimal("Infinity"), b"raw"):
            with self.assertRaises(DemoError):
                scalar(value)
        self.aggregate()
        query = self.plan["queries"][0]
        with self.assertRaisesRegex(DemoError, "absent"):
            aggregate_sql(self.config, query, [])
        with self.assertRaisesRegex(DemoError, "numeric"):
            aggregate_sql(self.config, query, [
                {"COLUMN_NAME": "Amount", "DATA_TYPE": "varchar"}])

    def test_relationship_validation_and_live_type_checks(self):
        config = copy.deepcopy(self.config)
        config["existing_data"]["tables"].append({"name": "customers", "purpose": "Parent"})
        plan = copy.deepcopy(self.plan)
        query = plan["queries"][0]
        query.update(kind="relationship", relationship={
            "column": "Customer Key", "parent_table": "customers", "parent_column": "Customer Key"})
        from demo_accelerator.sql_runner import validate_plan
        state = read(self.root)[1]
        validate_plan(config, state, plan)
        metadata = [{"COLUMN_NAME": "Customer Key", "DATA_TYPE": "int"}]
        sql, params = relationship_sql(config, query, metadata, metadata)
        self.assertIn("NOT EXISTS", sql)
        self.assertNotIn(" JOIN ", sql)
        self.assertEqual(params, ())
        with self.assertRaisesRegex(DemoError, "types differ"):
            relationship_sql(config, query, metadata, [
                {"COLUMN_NAME": "Customer Key", "DATA_TYPE": "varchar"}])
        with self.assertRaisesRegex(DemoError, "absent"):
            relationship_sql(config, query, metadata, [])
        for parent in ("unknown", "orders", None, []):
            invalid = copy.deepcopy(plan)
            invalid["queries"][0]["relationship"]["parent_table"] = parent
            with self.assertRaises(DemoError):
                validate_plan(config, state, invalid)
        query["filters"] = [{"column": "Customer Key", "op": ">", "value": 0}]
        with self.assertRaisesRegex(DemoError, "full-table"):
            validate_plan(config, state, plan)

    def test_relationship_counts_do_not_multiply_children_with_duplicate_parents(self):
        query = {"table": "orders", "relationship": {
            "column": "Customer Key", "parent_table": "customers", "parent_column": "Customer Key"}}
        metadata = [{"COLUMN_NAME": "Customer Key", "DATA_TYPE": "int"}]
        sql, _ = relationship_sql(self.config, query, metadata, metadata)
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("ATTACH DATABASE ':memory:' AS demo_customer")
            connection.execute("CREATE TABLE demo_customer.orders ([Customer Key] int)")
            connection.execute("CREATE TABLE demo_customer.customers ([Customer Key] int)")
            connection.executemany("INSERT INTO demo_customer.orders VALUES (?)",
                                   [(1,), (1,), (2,), (3,), (None,)])
            connection.executemany("INSERT INTO demo_customer.customers VALUES (?)",
                                   [(1,), (1,), (2,), (None,)])
            # COUNT_BIG has the same counting semantics; SQLite uses COUNT.
            result = connection.execute(sql.replace("COUNT_BIG", "COUNT")).fetchone()
            self.assertEqual(result, (5, 1, 1, 4, 1, 2))
        finally:
            connection.close()


class OdbcTests(unittest.TestCase):
    def fake_odbc(self):
        module = MagicMock()
        module.Error = type("OdbcError", (Exception,), {})
        module.drivers.return_value = ["ODBC Driver 18 for SQL Server"]
        connection = module.connect.return_value
        connection.cursor.return_value.description = [("total",)]
        connection.cursor.return_value.fetchmany.return_value = [(Decimal("10.25"),)]
        return module, connection

    def test_odbc_token_layout_timeout_and_connection_encryption(self):
        module, connection = self.fake_odbc()
        with patch("shutil.which", return_value="az"), patch(
                "subprocess.run", return_value=MagicMock(returncode=0, stdout="fake-token\n")), patch(
                "importlib.import_module", return_value=module):
            session = OdbcSession("example.datawarehouse.fabric.microsoft.com", "demo", 60)
        args, kwargs = module.connect.call_args
        self.assertIn("Encrypt=yes;TrustServerCertificate=no", args[0])
        self.assertNotIn("fake-token", args[0])
        self.assertEqual(kwargs["timeout"], 60)
        self.assertEqual(connection.timeout, 60)
        token = "fake-token".encode("utf-16-le")
        self.assertTrue(kwargs["attrs_before"][1256] == struct.pack("<I", len(token)) + token)
        self.assertEqual(session.query("SELECT SUM([x])", (), 100), [{"total": "10.25"}])
        connection.cursor.return_value.fetchmany.assert_called_with(101)

    def test_overflow_fails_without_returning_truncated_results(self):
        module, connection = self.fake_odbc()
        session = OdbcSession.__new__(OdbcSession)
        session.odbc, session.connection = module, connection
        connection.cursor.return_value.fetchmany.return_value = [(1,), (2,)]
        with self.assertRaisesRegex(DemoError, "exceeds"):
            session.query("catalog query", (), 1)
        connection.cursor.return_value.close.assert_called_once()

    def test_driver_error_redaction_and_cursor_cleanup(self):
        module, connection = self.fake_odbc()
        session = OdbcSession.__new__(OdbcSession)
        session.odbc, session.connection = module, connection
        connection.cursor.return_value.execute.side_effect = module.Error("sensitive driver detail")
        with self.assertRaisesRegex(DemoError, "remote cancellation") as caught:
            session.query("reviewed query", (), 100)
        self.assertNotIn("sensitive", str(caught.exception))
        connection.cursor.return_value.close.assert_called_once()

    def test_missing_optional_dependency_is_actionable(self):
        with patch("importlib.import_module", side_effect=ImportError):
            with self.assertRaisesRegex(DemoError, "optional SQL extra"):
                OdbcSession("server", "database", 60)


if __name__ == "__main__":
    unittest.main()
