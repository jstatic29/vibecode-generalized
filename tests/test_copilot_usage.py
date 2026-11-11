import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from demo_accelerator.cli import main
from demo_accelerator.config import DemoError
from demo_accelerator.copilot_usage import read_export, read_session


def checkpoint(total=1250000000, status="complete", watermarks=None):
    return {
        "type": "session.usage_checkpoint", "timestamp": "2026-11-11T14:00:00Z",
        "data": {"accountingSnapshot": {"totalNanoAiu": total, "aiCreditsStatus": status},
                 "usageAccountingWatermarks": {"main": 3} if watermarks is None else watermarks},
    }


def record(sequence, total=100000000, source="main", status="complete"):
    return {
        "type": "session.usage_record", "timestamp": "2026-11-11T14:01:00Z",
        "data": {"usage": {"accounting": {"sourceSessionId": source, "sequence": sequence},
                           "copilotUsage": {"totalNanoAiu": total}, "aiCreditsStatus": status}},
    }


class CopilotUsageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.session = Path(self.folder.name) / "session-test"
        self.session.mkdir()

    def write_events(self, events):
        path = self.session / "events.jsonl"
        path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        return path

    def test_native_checkpoint_and_new_records_include_children_once(self):
        self.write_events([
            record(1, total=9000000000),
            checkpoint(),
            record(3),
            record(4),
            record(4),
            record(1, source="child"),
            {"type": "assistant.message", "data": {"content": "private transcript"}},
        ])
        result = read_session(self.session)
        self.assertEqual(result["reported_ai_credits"], "1.450000000")
        self.assertEqual(result["total_nano_aiu"], 1450000000)
        self.assertEqual(result["worksheet_entry"]["credits"], "1.450000000")
        self.assertEqual(result["ai_credits_status"], "complete")
        self.assertNotIn("private transcript", json.dumps(result))

    def test_new_checkpoint_replaces_earlier_replay(self):
        self.write_events([checkpoint(), record(4), checkpoint(2000000000, watermarks={"main": 4}),
                           record(4), record(5)])
        self.assertEqual(read_session(self.session)["total_nano_aiu"], 2100000000)

    def test_partial_missing_and_zero_are_distinct(self):
        for total, status, expected in (
            (0, "complete", "0.000000000"),
            (1250000000, "partial", "1.250000000"),
            (None, "unavailable", None),
            (0, "unavailable", None),
        ):
            with self.subTest(status=status):
                self.write_events([checkpoint(total, status)])
                result = read_session(self.session)
                self.assertEqual(result["reported_ai_credits"], expected)
                self.assertEqual(result["worksheet_entry"]["credits"],
                                 expected if status == "complete" else None)
        self.write_events([checkpoint(), record(4, total=None, status="unavailable")])
        result = read_session(self.session)
        self.assertEqual(result["ai_credits_status"], "partial")
        self.assertIsNone(result["worksheet_entry"]["credits"])

    def test_unknown_formats_gaps_and_torn_writes_fail_explicitly(self):
        for events in (
            [record(1)],
            [checkpoint(), record(5)],
            [checkpoint(status="unknown")],
            [checkpoint(total=None)],
            [checkpoint(total=-1)],
            [checkpoint(total=True)],
            [checkpoint(total=1.5)],
            [checkpoint(), {"type": "session.usage_record", "data": {"usage": {}}}],
        ):
            self.write_events(events)
            with self.subTest(events=events), self.assertRaises(DemoError):
                read_session(self.session)
        path = self.write_events([checkpoint()])
        with path.open("a", encoding="utf-8") as stream:
            stream.write('{"type":')
        with self.assertRaisesRegex(DemoError, "retry after the turn ends"):
            read_session(self.session)

    def test_native_export_credits_not_premium_request_multiplier(self):
        path = self.session / "native-usage.json"
        path.write_text(json.dumps({
            "totalNanoAiu": 1234567890, "aiCreditsStatus": "complete",
            "totalPremiumRequestCost": 42, "modelMetrics": {}, "agentMetrics": {},
        }), encoding="utf-8")
        result = read_export(path, "pilot")
        self.assertEqual(result["reported_ai_credits"], "1.234567890")
        for data in (
            {"totalPremiumRequestCost": 42},
            {"totalNanoAiu": 1234567890},
            {"totalNanoAiu": None, "aiCreditsStatus": "complete"},
        ):
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.subTest(data=data), self.assertRaises(DemoError):
                read_export(path, "pilot")

    def test_cli_capture_without_model_call_and_refuses_overwrite(self):
        source = self.write_events([checkpoint()])
        before = source.read_bytes()
        output = self.session / "credits.json"
        args = ["pilot-copilot-usage", "--session-dir", str(self.session),
                "--output", str(output)]
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(stdout.getvalue())["reported_ai_credits"], "1.250000000")
        self.assertEqual(source.read_bytes(), before)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 1)
            self.assertEqual(main(["pilot-copilot-usage", "--usage-file", str(output),
                                   "--output", str(self.session / "invalid.json")]), 1)
        self.assertFalse((self.session / "invalid.json").exists())


if __name__ == "__main__":
    unittest.main()
