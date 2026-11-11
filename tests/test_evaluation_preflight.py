import runpy
import unittest
from pathlib import Path
from unittest.mock import Mock


HELPER = Path(__file__).resolve().parents[1] / ".github" / "skills" / "fabric-demo-companion" / "templates" / "evaluation-preflight.py"
check_destination = runpy.run_path(str(HELPER))["check_evaluation_destination"]


class EvaluationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.spark = Mock()
        self.spark.catalog.tableExists.return_value = False
        self.context = {"defaultLakehouseId": "lakehouse", "defaultLakehouseWorkspaceId": "workspace",
                        "defaultLakehouseName": "demo_lakehouse"}

    def check(self, **overrides):
        params = dict(spark=self.spark, context=self.context, workspace_id="workspace",
                      lakehouse_id="lakehouse", lakehouse_name="demo_lakehouse",
                      table_name="pilot_evaluation")
        return check_destination(**dict(params, **overrides))

    def test_checks_actual_summary_and_steps_namespace_before_legacy(self):
        self.assertEqual(self.check(), ("`demo_lakehouse`.`eval_result`.`pilot_evaluation`",
                                        "`demo_lakehouse`.`eval_result`.`pilot_evaluation_steps`"))
        self.assertEqual([call.args[0] for call in self.spark.catalog.tableExists.call_args_list], [
            "`demo_lakehouse`.`eval_result`.`pilot_evaluation`",
            "`demo_lakehouse`.`eval_result`.`pilot_evaluation_steps`",
            "`demo_lakehouse`.`dbo`.`pilot_evaluation`",
            "`demo_lakehouse`.`dbo`.`pilot_evaluation_steps`",
        ])
        self.spark.sql.assert_not_called()

    def test_existing_summary_steps_or_legacy_table_prevents_reuse(self):
        for schema, suffix in (("eval_result", ""), ("eval_result", "_steps"),
                               ("dbo", ""), ("dbo", "_steps")):
            target = f"`demo_lakehouse`.`{schema}`.`pilot_evaluation{suffix}`"
            self.spark.catalog.tableExists.side_effect = lambda name: name == target
            with self.subTest(target=target), self.assertRaisesRegex(RuntimeError, "refusing reuse"):
                self.check()

    def test_wrong_identity_or_unsafe_name_fails_before_catalog_access(self):
        for override in (
            {"lakehouse_id": "other"}, {"workspace_id": ""},
            {"lakehouse_name": "wrong_destination"},
            {"context": {}}, {"table_name": "schema.table"},
            {"lakehouse_name": "lakehouse`;DROP TABLE x"},
        ):
            self.spark.catalog.tableExists.reset_mock()
            with self.subTest(override=override), self.assertRaises((ValueError, RuntimeError)):
                self.check(**override)
            self.spark.catalog.tableExists.assert_not_called()

    def test_catalog_failure_is_not_treated_as_an_empty_destination(self):
        self.spark.catalog.tableExists.side_effect = RuntimeError("catalog unavailable")
        with self.assertRaisesRegex(RuntimeError, "catalog unavailable"):
            self.check()


if __name__ == "__main__":
    unittest.main()
