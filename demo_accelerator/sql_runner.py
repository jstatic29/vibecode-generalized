"""Opt-in, approval-bound TDS assessment; never accept arbitrary SQL."""

import hashlib
import importlib
import json
import math
import re
import shutil
import struct
import subprocess
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .config import DemoError, _keys, _text, digest, existing_mode
from .fabric import Client
from .state import audit, now, read, require_gate, save


IDENTITY_SQL = (
    "SELECT SUSER_SNAME() AS execution_login, USER_NAME() AS database_user, "
    "DB_NAME() AS database_name"
)
NUMERIC = {"bigint", "int", "smallint", "tinyint", "decimal", "numeric",
           "float", "real", "money", "smallmoney"}
ORDERED = NUMERIC | {"date", "datetime2", "datetime", "smalldatetime", "time"}


def quote(value):
    # Source column names can contain spaces; brackets are escaped, never interpolated as SQL.
    _text(value, "SQL identifier", 128)
    if any(ord(c) < 32 for c in value):
        raise DemoError("Control characters are not allowed in SQL identifiers")
    return "[" + value.replace("]", "]]") + "]"


def scalar(value):
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise DemoError("Nonfinite SQL result")
        return str(value)  # Preserve exact monetary precision.
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise DemoError("Unsupported or nonfinite SQL result type; no result persisted")


def context(root, assessment=False):
    config, state = read(root)
    if not existing_mode(config):
        raise DemoError("SQL runner requires existing-lakehouse mode")
    if state["gates"]["shortcuts"]["status"] != "complete":
        raise DemoError("Complete shortcuts and source-read-only identity review first")
    if assessment:
        require_gate(state, "data-readiness", approved=True)
    return config, state


def validate_plan(config, state, plan):
    _keys(plan, ["version", "config_hash", "inventory_sha256", "expected_login", "queries"],
          "SQL assessment plan")
    if type(plan.get("version")) is not int or plan["version"] != 1:
        raise DemoError("SQL assessment plan version must be 1")
    if plan.get("config_hash") != state["config_hash"]:
        raise DemoError("SQL plan config_hash does not match run")
    if plan.get("inventory_sha256") != state["resources"].get("shortcut_inventory", {}).get("sha256"):
        raise DemoError("SQL plan shortcut inventory does not match run")
    _text(plan.get("expected_login"), "expected_login", 254)
    if not re.fullmatch(r"[^;\s{}]+@[^;\s{}]+", plan["expected_login"]):
        raise DemoError("expected_login must be the approved Entra user principal name")
    queries = plan.get("queries")
    if not isinstance(queries, list) or not queries:
        raise DemoError("SQL assessment plan needs reviewed queries")
    aliases = {t["name"] for t in config["existing_data"]["tables"]}
    seen = set()
    for query in queries:
        _keys(query, ["id", "kind", "table", "measures", "filters", "scan_budget",
                      "disclosure", "relationship"], "SQL query")
        name = query.get("id")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name) or name in seen:
            raise DemoError("SQL query ids must be unique lowercase identifiers")
        seen.add(name)
        if not isinstance(query.get("table"), str) or query["table"] not in aliases:
            raise DemoError("SQL query table is not an approved shortcut alias")
        _text(query.get("scan_budget"), "query.scan_budget", 2000)
        _text(query.get("disclosure"), "query.disclosure", 2000)
        kind = query.get("kind")
        measures, filters = query.get("measures", []), query.get("filters", [])
        if not isinstance(measures, list) or not isinstance(filters, list):
            raise DemoError("measures and filters must be lists")
        if kind != "relationship" and "relationship" in query:
            raise DemoError("relationship is only valid for relationship queries")
        if kind == "relationship":
            if measures or filters:
                raise DemoError("Relationship checks use full-table counts, not measures or filters")
            relationship = query.get("relationship")
            _keys(relationship, ["column", "parent_table", "parent_column"], "SQL relationship")
            parent = relationship.get("parent_table")
            if not isinstance(parent, str) or parent not in aliases or parent == query["table"]:
                raise DemoError("Relationship parent must be a different approved shortcut table")
            quote(relationship.get("column"))
            quote(relationship.get("parent_column"))
        elif kind == "columns":
            if measures or filters:
                raise DemoError("Column metadata queries cannot include measures or filters")
        elif kind == "aggregate":
            if not measures or len(measures) > config["scope"]["max_result_rows"]:
                raise DemoError("Aggregate queries need a bounded list of measures")
            output_names = set()
            for measure in measures:
                _keys(measure, ["name", "function", "column"], "SQL measure")
                name = measure.get("name")
                if (not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name)
                        or name in output_names):
                    raise DemoError("Measure names must be unique lowercase identifiers")
                output_names.add(name)
                function = measure.get("function")
                if (not isinstance(function, str)
                        or function not in {"count_rows", "count_distinct", "null_count", "sum", "min", "max"}):
                    raise DemoError("Unsupported aggregate function")
                if function == "count_rows":
                    if "column" in measure:
                        raise DemoError("count_rows cannot specify a column")
                else:
                    quote(measure.get("column"))
            for condition in filters:
                _keys(condition, ["column", "op", "value"], "SQL filter")
                quote(condition.get("column"))
                if (not isinstance(condition.get("op"), str)
                        or condition["op"] not in {"=", "<>", ">", ">=", "<", "<="}):
                    raise DemoError("Unsupported SQL filter operator")
                value = condition.get("value")
                if (type(value) not in {str, int, float, bool}
                        or (type(value) is float and not math.isfinite(value))):
                    raise DemoError("SQL filter values must be finite scalar parameters")
        else:
            raise DemoError("Only columns, aggregate and relationship queries are supported")
    return plan


def preview(root, plan):
    config, state = context(root)
    validate_plan(config, state, plan)
    return {"plan_sha256": digest(plan), "scope": config["scope"], "plan": plan,
            "limitations": "No arbitrary SQL, raw rows or grouping; relationships use fixed count-only "
                           "EXISTS checks, not general joins. Scan budgets are "
                           "owner-reviewed, not a byte-scan quota. Timeout is per statement."}


def approve_plan(root, plan, note):
    config, state = context(root, assessment=True)
    validate_plan(config, state, plan)
    _text(note, "SQL plan approval note", 4000)
    sha = digest(plan)
    relative = f"evidence/sql-plan-{sha}.json"
    target = Path(root) / relative
    if target.exists():
        raise DemoError("This SQL plan is already approved; retain its existing evidence")
    target.parent.mkdir(exist_ok=True)
    save(target, {"kind": "operator-approved-sql-plan", "approved_at": now(),
                  "note": note, "plan": plan})
    state["resources"].setdefault("sql_plans", {})[sha] = {
        "evidence": relative, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    audit(root, state, "approve-sql-plan", "data-readiness", plan_sha256=sha)
    return {"status": "approved", "plan_sha256": sha, "evidence": relative}


class OdbcSession:
    """Azure CLI token stays in memory; ODBC enforces a per-statement timeout."""

    def __init__(self, server, database, timeout):
        try:
            self.odbc = importlib.import_module("pyodbc")
        except ImportError as exc:
            raise DemoError("Install the optional SQL extra: python -m pip install -e '.[sql]'") from exc
        driver = "ODBC Driver 18 for SQL Server"
        if driver not in self.odbc.drivers():
            raise DemoError("Install Microsoft ODBC Driver 18 for SQL Server before using the SQL runner")
        az = shutil.which("az")
        if not az:
            raise DemoError("Azure CLI is required; sign in using the approved isolated profile")
        auth = subprocess.run(
            [az, "account", "get-access-token", "--resource", "https://database.windows.net/",
             "--query", "accessToken", "--output", "tsv"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if auth.returncode or not auth.stdout.strip():
            raise DemoError("SQL token acquisition failed; interactively sign in to the approved profile")
        token = auth.stdout.strip().encode("utf-16-le")
        attributes = {1256: struct.pack("<I", len(token)) + token}
        connection_string = (
            f"DRIVER={{{driver}}};SERVER={server},1433;"
            f"DATABASE={{{database.replace('}', '}}')}}};Encrypt=yes;"
            "TrustServerCertificate=no;APP=FabricDemoAssessment;"
        )
        self.connection = None
        try:
            self.connection = self.odbc.connect(
                connection_string, attrs_before=attributes, timeout=timeout, autocommit=True)
            self.connection.timeout = timeout
            if self.connection.timeout != timeout:
                self.connection.close()
                raise DemoError("ODBC did not retain the required query timeout")
        except self.odbc.Error as exc:
            if self.connection is not None:
                self.close()
            raise DemoError("SQL connection failed; inspect authentication, endpoint and ODBC configuration") from exc

    def query(self, sql, parameters, limit):
        cursor = None
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, *parameters)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(limit + 1)
            if len(rows) > limit:
                raise DemoError("SQL result exceeds approved row limit; narrow the plan, no results saved")
            return [dict(zip(columns, (scalar(value) for value in row))) for row in rows]
        except self.odbc.Error as exc:
            # Driver messages can contain SQL values, principals or connection details.
            raise DemoError("SQL statement failed or timed out; remote cancellation is not confirmed. "
                            "Inspect the saved request before an explicit retry") from exc
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except self.odbc.Error as exc:
                    raise DemoError("SQL cursor cleanup failed; inspect the saved request before retrying") from exc

    def close(self):
        try:
            self.connection.close()
        except self.odbc.Error as exc:
            raise DemoError("SQL connection cleanup failed; remote session termination is unconfirmed") from exc


def endpoint(config, state, client):
    wid, lid = state["resources"]["workspace_id"], state["resources"]["lakehouse_id"]
    _, _, item = client.request("GET", f"/v1/workspaces/{wid}/lakehouses/{lid}")
    if item.get("id") != lid or item.get("displayName") != config["deployment"]["lakehouse_name"]:
        raise DemoError("Live lakehouse identity differs from approved destination")
    properties = item.get("properties", {}).get("sqlEndpointProperties", {})
    server = properties.get("connectionString", "")
    if (properties.get("provisioningStatus") != "Success"
            or not properties.get("id")
            or not re.fullmatch(r"[a-zA-Z0-9-]+\.datawarehouse\.fabric\.microsoft\.com", server)):
        raise DemoError("SQL endpoint is not ready or its server is outside the validated Fabric SQL host")
    return server, item["displayName"], properties["id"]


def verify_identity(session, expected, database):
    rows = session.query(IDENTITY_SQL, (), 1)
    if (len(rows) != 1 or rows[0].get("execution_login", "").casefold() != expected.casefold()
            or rows[0].get("database_user", "").casefold() != expected.casefold()
            or rows[0].get("database_name") != database):
        raise DemoError("SQL session identity/database mismatch; no assessment queries executed")
    return rows[0]


def columns_sql(config, table, limit):
    return (
        f"SELECT TOP ({limit + 1}) COLUMN_NAME, DATA_TYPE, IS_NULLABLE, ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? "
        "ORDER BY ORDINAL_POSITION",
        (config["deployment"]["schema"], table),
    )


def aggregate_sql(config, query, columns):
    types = {row["COLUMN_NAME"]: row["DATA_TYPE"].lower() for row in columns}

    def column(name):
        if name not in types:
            raise DemoError("Plan references a column absent from live approved table metadata")
        return quote(name)

    expressions = []
    for measure in query["measures"]:
        function = measure["function"]
        name = measure.get("column")
        col = column(name) if function != "count_rows" else None
        if function in {"sum", "min", "max"}:
            if types[name] not in (NUMERIC if function == "sum" else ORDERED):
                raise DemoError("SUM requires numeric columns; MIN/MAX require numeric or date/time columns")
        if function == "count_rows":
            expression = "COUNT_BIG(*)"
        elif function == "count_distinct":
            expression = f"COUNT_BIG(DISTINCT {col})"
        elif function == "null_count":
            expression = f"COUNT_BIG(*) - COUNT_BIG({col})"
        else:
            expression = f"{function.upper()}({col})"
        expressions.append(f"{expression} AS {quote(measure['name'])}")
    parameters, predicates = [], []
    for condition in query.get("filters", []):
        predicates.append(f"{column(condition['column'])} {condition['op']} ?")
        parameters.append(condition["value"])
    sql = ("SELECT " + ", ".join(expressions) + " FROM "
           + quote(config["deployment"]["schema"]) + "." + quote(query["table"]))
    if predicates:
        sql += " WHERE " + " AND ".join(predicates)
    return sql, tuple(parameters)


def relationship_sql(config, query, columns, parent_columns):
    relationship = query["relationship"]
    child_name, parent_name = relationship["column"], relationship["parent_column"]
    child_types = {row["COLUMN_NAME"]: row["DATA_TYPE"].lower() for row in columns}
    parent_types = {row["COLUMN_NAME"]: row["DATA_TYPE"].lower() for row in parent_columns}
    if child_name not in child_types or parent_name not in parent_types:
        raise DemoError("Relationship column absent from live approved table metadata")
    if child_types[child_name] != parent_types[parent_name]:
        raise DemoError("Relationship key types differ; explicit reviewed mapping is required")
    if child_types[child_name] not in NUMERIC | {"date", "uniqueidentifier", "varchar", "char"}:
        raise DemoError("Unsupported relationship key type")
    schema = quote(config["deployment"]["schema"])
    child = schema + "." + quote(query["table"])
    parent = schema + "." + quote(relationship["parent_table"])
    ck, pk = quote(child_name), quote(parent_name)
    # EXISTS preserves child grain even when a parent key is duplicated.
    return (
        f"SELECT (SELECT COUNT_BIG(*) FROM {child}) AS [child_rows], "
        f"(SELECT COUNT_BIG(*) FROM {child} AS c WHERE c.{ck} IS NULL) AS [null_child_keys], "
        f"(SELECT COUNT_BIG(*) FROM {child} AS c WHERE c.{ck} IS NOT NULL AND "
        f"NOT EXISTS (SELECT 1 FROM {parent} AS p WHERE p.{pk} = c.{ck})) AS [orphan_rows], "
        f"(SELECT COUNT_BIG(*) FROM {parent}) AS [parent_rows], "
        f"(SELECT COUNT_BIG(*) FROM {parent} AS p WHERE p.{pk} IS NULL) AS [null_parent_keys], "
        f"(SELECT COUNT_BIG(DISTINCT p.{pk}) FROM {parent} AS p) AS [distinct_parent_keys]",
        (),
    )


def run(root, expected_login=None, plan=None, client=None, session_factory=None,
        inventory_client=None):
    """Without a plan, run identity-only preflight; never read source data."""
    config, state = context(root, assessment=plan is not None)
    if plan is not None:
        validate_plan(config, state, plan)
        sha = digest(plan)
        approval = state["resources"].get("sql_plans", {}).get(sha)
        if not approval:
            raise DemoError("Explicitly approve the exact SQL plan before execution")
        approved = json.loads((Path(root) / approval["evidence"]).read_text(encoding="utf-8"))
        if approved["plan"] != plan:
            raise DemoError("SQL plan differs from approved evidence")
        expected_login = plan["expected_login"]
        from .existing_data import shortcut_bindings
        inventory = state["resources"]["shortcut_inventory"]
        original = json.loads((Path(root) / inventory["evidence"]).read_text(encoding="utf-8"))
        wid, lid = state["resources"]["workspace_id"], state["resources"]["lakehouse_id"]
        live = (inventory_client or Client(skill="onelake-catalog-cli")).listing(
            f"/v1/workspaces/{wid}/items/{lid}/shortcuts")
        if shortcut_bindings(config, state["resources"], live) != original["bindings"]:
            raise DemoError("Shortcut targets drifted since approval; stop and review source permissions")
    _text(expected_login, "expected_login", 254)
    client = client or Client(skill="sqldw-cli")
    server, database, endpoint_id = endpoint(config, state, client)
    relative = f"evidence/sql-execution-{uuid.uuid4().hex}.json"
    receipt = {
        "kind": "machine-sql-execution", "started_at": now(), "status": "started",
        "config_hash": state["config_hash"], "sql_endpoint_id": endpoint_id,
        "workspace_id": state["resources"]["workspace_id"],
        "lakehouse_id": state["resources"]["lakehouse_id"],
        "plan_sha256": digest(plan) if plan is not None else None,
        "query_timeout_seconds": config["scope"]["max_query_seconds"],
        "max_result_rows": config["scope"]["max_result_rows"], "queries": [],
        "limitation": "ODBC command timeout requests cancellation; it does not prove remote "
                      "termination. Scan budgets and source-read-only permissions are owner-reviewed.",
    }
    path = Path(root) / relative
    path.parent.mkdir(exist_ok=True)
    save(path, receipt)
    session = None
    try:
        session = (session_factory or OdbcSession)(server, database, config["scope"]["max_query_seconds"])
        receipt["identity"] = verify_identity(session, expected_login, database)
        save(path, receipt)
        limit = config["scope"]["max_result_rows"]
        for query in plan["queries"] if plan is not None else []:
            # Verify each time, not just once at process startup.
            verify_identity(session, expected_login, database)
            entry = {"id": query["id"], "started_at": now(), "status": "started"}
            receipt["queries"].append(entry)
            save(path, receipt)
            sql, parameters = columns_sql(config, query["table"], limit)
            entry.update(metadata_sql=sql, metadata_parameters=list(parameters))
            save(path, receipt)
            columns = session.query(sql, parameters, limit)
            if not columns:
                raise DemoError("Approved shortcut table has no visible columns")
            if query["kind"] == "aggregate":
                sql, parameters = aggregate_sql(config, query, columns)
                entry.update(sql=sql, parameters=list(parameters))
                save(path, receipt)
                rows = session.query(sql, parameters, limit)
            elif query["kind"] == "relationship":
                sql, parameters = columns_sql(config, query["relationship"]["parent_table"], limit)
                entry.update(parent_metadata_sql=sql, parent_metadata_parameters=list(parameters))
                save(path, receipt)
                parent_columns = session.query(sql, parameters, limit)
                sql, parameters = relationship_sql(config, query, columns, parent_columns)
                entry.update(sql=sql, parameters=list(parameters))
                save(path, receipt)
                rows = session.query(sql, parameters, limit)
            else:
                rows = columns
            entry.update(status="succeeded", completed_at=now(), sql=sql,
                         parameters=list(parameters), rows=rows)
            save(path, receipt)
        closing, session = session, None
        closing.close()
        receipt.update(status="succeeded", completed_at=now())
        save(path, receipt)
        audit(root, state, "sql-execution", "data-readiness", evidence=relative,
              plan_sha256=receipt["plan_sha256"], identity_only=plan is None)
        return {"status": "succeeded", "evidence": relative, "identity_only": plan is None,
                "queries_completed": len(receipt["queries"])}
    except (DemoError, OSError, ValueError, subprocess.SubprocessError) as exc:
        receipt.update(status="failed-remote-status-unconfirmed", completed_at=now(),
                       error="Execution failed; no automatic retry. Review request and source status.")
        save(path, receipt)
        audit(root, state, "sql-execution-failed", "data-readiness", evidence=relative)
        raise DemoError(f"SQL runner stopped. Evidence: {relative}. {exc}") from exc
    finally:
        if session is not None:
            session.close()
