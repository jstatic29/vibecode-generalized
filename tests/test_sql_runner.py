import copy
import json
import sqlite3
import struct
import tempfile
import unittest
from decimal import Decimal
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from demo_accelerator.artifacts import generate
from demo_accelerator.cli import execute, parser
from demo_accelerator.config import DemoError, digest
from demo_accelerator.existing_data import evidence_fields, inspect_shortcuts, setup_lakehouse
from demo_accelerator.sql_runner import (
    IDENTITY_SQL, OdbcSession, aggregate_sql, approve_plan, preview, quote,
    relationship_sql, run, scalar, conversion_sql, check_conversions, check_results,
    date_formats_sql,
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

    def test_explicit_conversion_sql_and_fail_closed_quality(self):
        query = {"table": "orders", "conversions": [
            {"column": "Amount", "type": "decimal", "allow_null": False},
            {"column": "Order Date", "type": "iso_date", "allow_null": False},
        ]}
        metadata = [{"COLUMN_NAME": c["column"], "DATA_TYPE": "varchar"}
                    for c in query["conversions"]]
        sql, params = conversion_sql(self.config, query, metadata)
        self.assertEqual(params, ("Amount", "Order Date"))
        self.assertIn("TRY_CONVERT(decimal(28,6)", sql)
        self.assertIn("TRY_CONVERT(date,", sql)
        self.assertIn(", 23)", sql)
        self.assertIn("<= 6", sql)
        self.assertIn("LEN(", sql)
        self.assertIn("NULLIF(LTRIM(RTRIM(", sql)
        self.assertNotIn(" WHERE ", sql)  # Quality checks cover the whole table.
        rows = [{"column_name": c["column"], "invalid_count": 0, "null_count": 0}
                for c in query["conversions"]]
        check_conversions(query, rows)
        for field in ("invalid_count", "null_count"):
            bad = copy.deepcopy(rows)
            bad[0][field] = 1
            with self.assertRaisesRegex(DemoError, "quality failed"):
                check_conversions(query, bad)
        with self.assertRaisesRegex(DemoError, "does not match"):
            check_conversions(query, rows[:1])
        query["conversions"][0]["allow_null"] = True
        rows[0]["null_count"] = 1
        check_conversions(query, rows)

    def test_conversion_and_calendar_aggregate_are_explicit_and_parameterized(self):
        self.aggregate()
        query = self.plan["queries"][0]
        query.update(conversions=[
            {"column": "Amount", "type": "decimal", "allow_null": False},
            {"column": "Order Date", "type": "iso_date", "allow_null": False}],
            group_by=[{"column": "Order Date", "name": "year", "date_part": "year"},
                      {"column": "Order Date", "name": "month", "date_part": "month"}])
        preview(self.root, self.plan)
        metadata = [{"COLUMN_NAME": c["column"], "DATA_TYPE": "varchar"}
                    for c in query["conversions"]]
        sql, params = aggregate_sql(self.config, query, metadata)
        self.assertIn("SELECT TOP (101)", sql)
        self.assertIn("DATEPART(year,", sql)
        self.assertIn("DATEPART(month,", sql)
        self.assertIn("GROUP BY", sql)
        self.assertIn("ORDER BY [year], [month]", sql)
        self.assertIn("SUM(CASE", sql)
        self.assertEqual(params, ("2016-01-01", "2016-01-02"))

    def test_new_plan_fields_reject_unsafe_and_inconsistent_scope(self):
        self.aggregate()
        valid = copy.deepcopy(self.plan)
        valid["queries"][0]["conversions"] = [
            {"column": "Amount", "type": "decimal", "allow_null": False}]
        for update in (
                {"conversions": [{"column": "Amount", "type": "float", "allow_null": False}]},
                {"conversions": [{"column": "Amount", "type": [], "allow_null": False}]},
                {"conversions": [{"column": "Amount", "type": "decimal"}]},
                {"group_by": [{"column": "Amount", "name": "total"}]},
                {"group_by": [{"column": "Amount", "name": "x", "source": "parent"}]},
                {"group_by": [{"column": "Amount", "name": "x", "date_part": "EXEC"}]},
                {"join": {"column": "X", "parent_table": "other", "parent_column": "X"}},
                {"kind": "columns"},
                {"kind": "conversion"}):
            plan = copy.deepcopy(valid)
            plan["queries"][0].update(update)
            with self.subTest(update=update), self.assertRaises(DemoError):
                preview(self.root, plan)

    def test_conversion_failure_saves_counts_before_stopping_aggregate(self):
        self.aggregate()
        self.plan["queries"][0]["conversions"] = [
            {"column": "Amount", "type": "decimal", "allow_null": False}]
        self.authorize()
        def factory(server, database, timeout):
            session = self.factory(server, database, timeout)
            original = session.query
            def query(sql, params, limit):
                if "INFORMATION_SCHEMA.COLUMNS" in sql:
                    return [{"COLUMN_NAME": "Amount", "DATA_TYPE": "varchar"}]
                if "invalid_count" in sql:
                    session.calls.append((sql, params, limit))
                    return [{"column_name": "Amount", "invalid_count": 1, "null_count": 0}]
                return original(sql, params, limit)
            session.query = query
            return session
        with self.assertRaisesRegex(DemoError, "quality failed"):
            self.execute(self.plan, factory)
        self.assertFalse(any("SUM(" in c[0] for c in self.sessions[0].calls))
        receipt = json.loads(next((self.root / "evidence").glob("sql-execution-*")).read_text())
        self.assertEqual(receipt["queries"][0]["conversion_rows"][0]["invalid_count"], 1)
        self.assertEqual(receipt["queries"][0]["status"], "quality-failed")
        self.assertEqual(receipt["status"], "failed-quality-check")

    def test_result_checks_stop_remaining_queries_and_preserve_findings(self):
        self.aggregate()
        self.plan["queries"][0]["checks"] = [{"column": "total", "equals": "0"}]
        self.plan["queries"].append({
            "id": "later", "kind": "columns", "table": "orders",
            "scan_budget": "Catalog only", "disclosure": "Column metadata"})
        self.authorize()
        with self.assertRaisesRegex(DemoError, "remaining queries"):
            self.execute(self.plan)
        receipt = json.loads(next((self.root / "evidence").glob("sql-execution-*")).read_text())
        self.assertEqual(len(receipt["queries"]), 1)
        self.assertEqual(receipt["queries"][0]["status"], "quality-failed")
        self.assertEqual(receipt["queries"][0]["rows"], [{"total": "10.25"}])
        check_results({"checks": [{"column": "rows", "equals_column": "distinct"}]},
                      [{"rows": 2, "distinct": 2}])
        for rows in ([], [{"rows": 2}], [{"rows": None, "distinct": None}]):
            with self.assertRaises(DemoError):
                check_results({"checks": [{"column": "rows", "equals_column": "distinct"}]}, rows)

    def test_explicit_conversion_success_executes_sum_after_quality_receipt(self):
        self.aggregate()
        self.plan["queries"][0]["conversions"] = [
            {"column": "Amount", "type": "decimal", "allow_null": False}]
        self.authorize()
        def factory(server, database, timeout):
            session = self.factory(server, database, timeout)
            original = session.query
            def query(sql, params, limit):
                if "INFORMATION_SCHEMA.COLUMNS" in sql:
                    return [{"COLUMN_NAME": "Amount", "DATA_TYPE": "varchar"},
                            {"COLUMN_NAME": "Order Date", "DATA_TYPE": "date"}]
                if "invalid_count" in sql:
                    session.calls.append((sql, params, limit))
                    return [{"column_name": "Amount", "invalid_count": 0, "null_count": 0}]
                return original(sql, params, limit)
            session.query = query
            return session
        result = self.execute(self.plan, factory)
        self.assertEqual(result["status"], "succeeded")
        self.assertIn("SUM(CASE", self.sessions[0].calls[-1][0])

    def test_ratio_uses_sums_and_zero_guard_not_average_row_ratios(self):
        query = {"table": "orders", "measures": [
            {"name": "margin_pct", "function": "ratio_of_sums",
             "numerator": "Profit", "denominator": "Sales"}]}
        metadata = [{"COLUMN_NAME": c, "DATA_TYPE": "decimal"} for c in ("Profit", "Sales")]
        sql, params = aggregate_sql(self.config, query, metadata)
        self.assertIn("SUM([Profit])", sql)
        self.assertIn("NULLIF(CAST(SUM([Sales])", sql)
        self.assertNotIn("AVG(", sql)
        self.assertEqual(params, ())
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("ATTACH DATABASE ':memory:' AS demo_customer")
            connection.execute("CREATE TABLE demo_customer.orders (Profit real, Sales real)")
            connection.executemany("INSERT INTO demo_customer.orders VALUES (?,?)",
                                   [(10.0, 100.0), (50.0, 200.0), (-5.0, 0.0)])
            self.assertAlmostEqual(connection.execute(sql).fetchone()[0], 100 * 55 / 300)
            connection.execute("DELETE FROM demo_customer.orders")
            connection.execute("INSERT INTO demo_customer.orders VALUES (5.0, 0.0)")
            self.assertIsNone(connection.execute(sql).fetchone()[0])
        finally:
            connection.close()
        with self.assertRaisesRegex(DemoError, "numeric"):
            aggregate_sql(self.config, query, [
                {"COLUMN_NAME": c, "DATA_TYPE": "varchar"} for c in ("Profit", "Sales")])

    def test_iso_timestamp_date_is_explicit_midnight_only_without_timezone_guessing(self):
        query = {"table": "orders", "conversions": [
            {"column": "Order Date", "type": "iso_timestamp_date", "allow_null": False}]}
        metadata = [{"COLUMN_NAME": "Order Date", "DATA_TYPE": "varchar"}]
        sql, params = conversion_sql(self.config, query, metadata)
        self.assertIn("TRY_CONVERT(datetime2(6)", sql)
        self.assertIn(", 126)", sql)
        self.assertIn("= 'T'", sql)
        self.assertIn("= '00:00:00'", sql)
        self.assertIn("BETWEEN 21 AND 26", sql)
        self.assertIn("NOT LIKE '%[^0-9]%'", sql)
        self.assertEqual(params, ("Order Date",))
        query.update(measures=[{"name": "first_date", "function": "min", "column": "Order Date"}],
                     group_by=[{"column": "Order Date", "name": "month", "date_part": "month"}])
        aggregate, _ = aggregate_sql(self.config, query, metadata)
        self.assertIn("DATEPART(month,", aggregate)

    def test_date_format_diagnostic_is_count_only_and_does_not_choose_mapping(self):
        query = self.plan["queries"][0]
        query.update(kind="date_formats", date_columns=["Order Date"])
        preview(self.root, self.plan)
        sql, params = date_formats_sql(
            self.config, query, [{"COLUMN_NAME": "Order Date", "DATA_TYPE": "varchar"}])
        self.assertEqual(params, ("Order Date",))
        for style in (23, 126, 121, 101, 103, 112):
            self.assertIn(f", {style})", sql)
        self.assertIn("COUNT_BIG(CASE", sql)
        self.assertNotIn("GROUP BY", sql)
        self.assertNotIn("SELECT [Order Date]", sql)
        with self.assertRaisesRegex(DemoError, "text column"):
            date_formats_sql(self.config, query, [{"COLUMN_NAME": "Order Date", "DATA_TYPE": "date"}])
        query["date_columns"] = ["Order Date", "Order Date"]
        with self.assertRaisesRegex(DemoError, "unique"):
            preview(self.root, self.plan)

    def test_odbc_midnight_date_does_not_round_seventh_fraction_or_discard_time(self):
        query = {"table": "orders", "conversions": [
            {"column": "Order Date", "type": "odbc_midnight_date", "allow_null": False}]}
        sql, params = conversion_sql(
            self.config, query, [{"COLUMN_NAME": "Order Date", "DATA_TYPE": "varchar"}])
        self.assertIn("= 27", sql)
        self.assertIn("= ' 00:00:00.0000000'", sql)
        self.assertIn("TRY_CONVERT(date, LEFT(", sql)
        self.assertNotIn("TRY_CONVERT(datetime2", sql)
        self.assertEqual(params, ("Order Date",))
        connection = sqlite3.connect(":memory:")
        def try_date(value, style):
            try:
                return date.fromisoformat(value).isoformat() if value is not None else None
            except ValueError:
                return None
        try:
            connection.create_function("try_date", 2, try_date)
            connection.create_function("canonical_date", 2, lambda value, style: value)
            connection.create_function("left_text", 2, lambda value, n: value[:n] if value else value)
            connection.create_function("LEN", 1, lambda value: len(value) if value else None)
            connection.execute("ATTACH DATABASE ':memory:' AS demo_customer")
            connection.execute("CREATE TABLE demo_customer.orders ([Order Date] text)")
            connection.executemany("INSERT INTO demo_customer.orders VALUES (?)", [
                ("2016-02-29 00:00:00.0000000",),
                ("2016-02-30 00:00:00.0000000",),
                ("2016-01-01 01:00:00.0000000",),
                ("2016-01-01 00:00:00.0000001",),
                ("2016-01-01T00:00:00.0000000",),
                ("",), (None,),
            ])
            adapted = (sql.replace("COUNT_BIG", "COUNT")
                       .replace("TRY_CONVERT(date,", "try_date(")
                       .replace("CONVERT(varchar(10),", "canonical_date(")
                       .replace("LEFT(", "left_text("))
            self.assertEqual(connection.execute(adapted, params).fetchone(),
                             ("Order Date", 7, 1, 5))
        finally:
            connection.close()

    def test_grouped_join_executes_only_after_unique_nonorphan_parent_guard(self):
        query = {"table": "orders", "measures": [
            {"name": "total", "function": "sum", "column": "Amount"}],
            "group_by": [{"column": "Category", "name": "category", "source": "parent"}],
            "join": {"column": "Customer Key", "parent_table": "customers",
                     "parent_column": "Customer Key"}}
        columns = [{"COLUMN_NAME": "Amount", "DATA_TYPE": "decimal"},
                   {"COLUMN_NAME": "Customer Key", "DATA_TYPE": "int"}]
        parent = [{"COLUMN_NAME": "Category", "DATA_TYPE": "varchar"}]
        sql, params = aggregate_sql(self.config, query, columns, parent)
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("ATTACH DATABASE ':memory:' AS demo_customer")
            connection.execute("CREATE TABLE demo_customer.orders ([Customer Key] int, Amount int)")
            connection.execute("CREATE TABLE demo_customer.customers ([Customer Key] int, Category text)")
            connection.executemany("INSERT INTO demo_customer.orders VALUES (?,?)",
                                   [(1, 10), (1, -3), (2, 20), (None, 5)])
            connection.executemany("INSERT INTO demo_customer.customers VALUES (?,?)",
                                   [(1, "A"), (2, "B")])
            rows = connection.execute(sql.replace("TOP (101) ", ""), params).fetchall()
            self.assertEqual(rows, [(None, 5), ("A", 7), ("B", 20)])
        finally:
            connection.close()
        with self.assertRaisesRegex(DemoError, "parent metadata"):
            aggregate_sql(self.config, query, columns, [])

    def test_join_guard_stops_duplicate_or_orphan_results(self):
        self.aggregate()
        self.plan["queries"][0].update(
            join={"column": "Amount", "parent_table": "customers", "parent_column": "Amount"},
            group_by=[{"column": "Amount", "name": "amount_group", "source": "parent"}])
        config, state = read(self.root)
        config["existing_data"]["tables"].append({"name": "customers", "purpose": "Parent"})
        state["gates"]["data-readiness"]["status"] = "approved"
        with patch("demo_accelerator.sql_runner.context", return_value=(config, state)):
            approve_plan(self.root, self.plan, "Reviewed guarded aggregate")
        inventory = json.loads((self.root / state["resources"]["shortcut_inventory"]["evidence"]).read_text())
        # Exercise the guarded runtime without altering generated immutable configuration.
        for counts in (
                {"parent_rows": 2, "distinct_parent_keys": 1, "null_parent_keys": 0,
                 "orphan_rows": 0},
                {"parent_rows": 1, "distinct_parent_keys": 1, "null_parent_keys": 0,
                 "orphan_rows": 1}):
            with patch("demo_accelerator.sql_runner.context", return_value=(config, state)), patch(
                    "demo_accelerator.existing_data.shortcut_bindings",
                    return_value=inventory["bindings"]):
                def factory(server, database, timeout):
                    session = self.factory(server, database, timeout)
                    original = session.query
                    def query(sql, params, limit):
                        if "orphan_rows" in sql:
                            session.calls.append((sql, params, limit))
                            return [counts]
                        return original(sql, params, limit)
                    session.query = query
                    return session
                with self.assertRaisesRegex(DemoError, "Join quality failed"):
                    self.execute(self.plan, factory)
                self.assertFalse(any("LEFT JOIN" in c[0] for c in self.sessions[-1].calls))


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
