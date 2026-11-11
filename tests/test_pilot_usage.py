import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from demo_accelerator.cli import main
from demo_accelerator.config import DemoError
from demo_accelerator.pilot_usage import summarize, template


def measurements():
    data = template()
    data["window"] = {"start": "2026-11-11T09:00:00-06:00",
                      "end": "2026-11-11T12:00:00-06:00"}
    for row in (data["copilot"][0], data["fabric"][0]):
        row.update(evidence_ref="private-evidence.json", captured_at="2026-11-12T10:00:00Z")
    data["copilot"][0]["credits"] = "12.5"
    data["fabric"][0]["cu_seconds"] = "7200"
    return data


def rate(fabric=False):
    result = {"per_unit": "0.125", "currency": "USD",
              "source": "synthetic test rate, not a quoted price", "as_of": "2026-11-11"}
    if fabric:
        result["region"] = "test-region"
    return result


class PilotUsageTests(unittest.TestCase):
    def test_multiple_sessions_and_fabric_billing_modes_remain_separate(self):
        data = measurements()
        second = dict(data["copilot"][0], scope_ref="session-2", credits="0.2")
        data["copilot"].append(second)
        data["fabric"].extend([
            dict(data["fabric"][0], scope_ref="autoscale", billing_mode="spark-autoscale",
                 cu_seconds="1800"),
            dict(data["fabric"][0], scope_ref="preview", billing_mode="nonbillable",
                 cu_seconds="3600"),
        ])
        result = summarize(data)
        self.assertEqual(result["copilot"]["reported_credits"], "12.7")
        self.assertEqual(result["fabric"]["cu_hours_by_billing_mode"],
                         {"capacity": "2", "spark-autoscale": "0.5", "nonbillable": "1"})
        self.assertIsNone(result["copilot"]["estimated_cost_by_currency"])
        self.assertEqual(result["measurements"]["fabric"], data["fabric"])

    def test_missing_is_not_zero_and_shared_account_is_approximate(self):
        data = measurements()
        data["copilot"][0].update(credits="0", attribution="shared-account-delta")
        data["fabric"][0]["cu_seconds"] = None
        result = summarize(data)
        self.assertTrue(result["copilot"]["approximate"])
        self.assertEqual(result["copilot"]["reported_credits"], "0")
        self.assertIsNone(result["fabric"]["cu_seconds_by_billing_mode"])
        self.assertEqual(result["fabric"]["status"], "incomplete")
        data["copilot"] = []
        self.assertIsNone(summarize(data)["copilot"]["reported_credits"])

    def test_optional_rates_compute_exact_separate_allocation_estimates(self):
        data = measurements()
        data["copilot"][0]["rate"] = rate()
        data["fabric"][0]["rate"] = rate(True)
        data["fabric"].append(dict(
            data["fabric"][0], scope_ref="autoscale", billing_mode="spark-autoscale",
            cu_seconds="1800", rate=dict(rate(True), per_unit="0.25")))
        result = summarize(data)
        self.assertEqual(result["copilot"]["estimated_cost_by_currency"], {"USD": "1.5625"})
        self.assertEqual(result["fabric"]["estimated_cost_by_currency"], {"USD": "0.375"})
        data["fabric"][1]["rate"]["currency"] = "EUR"
        self.assertEqual(summarize(data)["fabric"]["estimated_cost_by_currency"],
                         {"EUR": "0.125", "USD": "0.250"})

    def test_partial_measurements_or_prices_do_not_produce_complete_cost(self):
        data = measurements()
        data["copilot"][0]["rate"] = rate()
        data["copilot"].append(dict(data["copilot"][0], scope_ref="session-2", rate=None))
        self.assertIsNone(summarize(data)["copilot"]["estimated_cost_by_currency"])
        data["copilot"][1]["credits"] = None
        self.assertEqual(summarize(data)["copilot"]["status"], "incomplete")
        self.assertIsNone(summarize(data)["copilot"]["estimated_cost_by_currency"])

    def test_reject_invalid_values_and_ambiguous_units(self):
        for value in (True, -1, "NaN", "Infinity", "invalid", {}, "1e100", "1e-100"):
            with self.subTest(value=value):
                data = measurements()
                data["copilot"][0]["credits"] = value
                with self.assertRaises(DemoError):
                    summarize(data)
        for group, field, value in (
            ("copilot", "attribution", "tokens"),
            ("fabric", "billing_mode", "unknown"),
            ("copilot", "evidence_ref", None),
            ("fabric", "captured_at", "2026-11-11T12:00:00"),
            ("fabric", "captured_at", "2026-11-10T12:00:00Z"),
        ):
            data = measurements()
            data[group][0][field] = value
            with self.subTest(field=field), self.assertRaises(DemoError):
                summarize(data)
        data = measurements()
        data["copilot"][0]["tokens"] = 100
        with self.assertRaises(DemoError):
            summarize(data)

    def test_reject_duplicate_scopes_invalid_windows_and_unsourced_rates(self):
        data = measurements()
        data["fabric"].append(copy.deepcopy(data["fabric"][0]))
        with self.assertRaisesRegex(DemoError, "Duplicate"):
            summarize(data)
        for window in (
            {"start": None, "end": None},
            {"start": "2026-11-11", "end": "2026-11-12"},
            {"start": "2026-11-12T00:00:00Z", "end": "2026-11-11T00:00:00Z"},
        ):
            data = measurements()
            data["window"] = window
            with self.assertRaises(DemoError):
                summarize(data)
        for field in ("region", "source", "as_of", "currency"):
            data = measurements()
            data["fabric"][0]["rate"] = rate(True)
            data["fabric"][0]["rate"][field] = ""
            with self.subTest(field=field), self.assertRaises(DemoError):
                summarize(data)
        data = measurements()
        data["fabric"][0].update(billing_mode="nonbillable", rate=rate(True))
        with self.assertRaisesRegex(DemoError, "Nonbillable"):
            summarize(data)

    def test_cli_writes_new_private_files_without_requiring_a_run(self):
        with tempfile.TemporaryDirectory() as folder:
            worksheet = Path(folder) / "operations" / "usage.json"
            output = worksheet.with_name("report.json")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["pilot-usage-template", "--output", str(worksheet)]), 0)
            self.assertIsNone(json.loads(worksheet.read_text())["copilot"][0]["credits"])
            worksheet.write_text(json.dumps(measurements()), encoding="utf-8-sig")
            original = worksheet.read_bytes()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["pilot-usage-report", str(worksheet),
                                       "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text())["copilot"]["reported_credits"], "12.5")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["pilot-usage-template", "--output", str(worksheet)]), 1)
                self.assertEqual(main(["pilot-usage-report", str(worksheet),
                                       "--output", str(output)]), 1)
            self.assertEqual(worksheet.read_bytes(), original)
            worksheet.write_text("{}", encoding="utf-8")
            invalid_output = worksheet.with_name("invalid-report.json")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["pilot-usage-report", str(worksheet),
                                       "--output", str(invalid_output)]), 1)
            self.assertFalse(invalid_output.exists())

    def test_cli_preserves_decimal_measurements_without_float_rounding(self):
        with tempfile.TemporaryDirectory() as folder:
            worksheet = Path(folder) / "usage.json"
            output = Path(folder) / "report.json"
            exact = "0.1234567890123456789012345678"
            text = json.dumps(measurements()).replace('"12.5"', exact)
            worksheet.write_text(text, encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["pilot-usage-report", str(worksheet),
                                       "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text())["copilot"]["reported_credits"], exact)


if __name__ == "__main__":
    unittest.main()
