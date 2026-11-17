import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from demo_accelerator.cli import main
from demo_accelerator.config import DemoError
from demo_accelerator.prerequisites import check, command_json


class PrerequisiteTests(unittest.TestCase):
    def commands(self, tool, args):
        if tool == "copilot":
            return "ok", [
                {"name": "fabric-skills", "enabled": True, "version": "0.3.22",
                 "path": "PRIVATE", "token": "PRIVATE"},
                {"name": "PRIVATE", "enabled": True, "version": "PRIVATE"},
            ]
        if args[0] == "version":
            return "ok", {"azure-cli": "2.92.0", "username": "PRIVATE"}
        if args[0] == "account" and args[1] == "show":
            return "ok", "user"
        return "ok", 9999999999

    def run_check(self, **kwargs):
        with patch("demo_accelerator.prerequisites.command_json", side_effect=self.commands), \
                patch("demo_accelerator.prerequisites.version", return_value="2.56.1"):
            return check(**kwargs)

    def test_sanitized_results_and_deferred_checks(self):
        report = self.run_check()
        checks = {c["check"]: c for c in report["checks"]}
        self.assertFalse(report["blocked"])
        self.assertFalse(report["complete"])
        self.assertNotIn("PRIVATE", json.dumps(report))
        self.assertEqual(checks["fabric-token"]["status"], "passed")
        self.assertEqual(checks["sql-endpoint-mcp"]["status"], "unverified")
        self.assertEqual(checks["modeling-mcp"]["status"], "not applicable")
        self.assertEqual(checks["workspace-capacity"]["status"], "unverified")

    def test_workspace_uses_existing_read_only_preflight_and_sanitizes_errors(self):
        for error in (None, DemoError("PRIVATE")):
            with self.subTest(error=error), patch(
                    "demo_accelerator.prerequisites.preflight", side_effect=error) as preflight:
                report = self.run_check(workspace="PRIVATE", client=object(),
                                        data_mode="existing-lakehouse", semantic_model=True)
                self.assertEqual(preflight.call_args.args[0]["deployment"]["workspace_name"], "PRIVATE")
                checks = {c["check"]: c for c in report["checks"]}
                self.assertEqual(checks["workspace-capacity"]["status"],
                                 "blocked" if error else "passed")
                self.assertEqual(checks["source-read-only"]["status"], "unverified")
                self.assertEqual(checks["modeling-mcp"]["status"], "unverified")
                self.assertNotIn("PRIVATE", json.dumps(report))

    def test_expired_token_stops_target_access(self):
        original = self.commands

        def commands(tool, args):
            return ("ok", 1) if "get-access-token" in args else original(tool, args)

        with patch.object(self, "commands", side_effect=commands), patch(
                "demo_accelerator.prerequisites.preflight") as preflight:
            report = self.run_check(workspace="PRIVATE")
            self.assertTrue(report["blocked"])
            preflight.assert_not_called()

    def test_missing_tools_and_unknown_plugin_format_are_not_passes(self):
        with patch("demo_accelerator.prerequisites.command_json", return_value=("missing", None)), \
                patch("demo_accelerator.prerequisites.version", return_value=None):
            report = check()
        checks = {c["check"]: c for c in report["checks"]}
        self.assertTrue(report["blocked"])
        self.assertEqual(checks["fabric-plugins"]["status"], "unverified")
        self.assertEqual(checks["azure-sign-in"]["status"], "unverified")
        with patch.object(self, "commands", return_value=("ok", {"unexpected": "PRIVATE"})):
            report = self.run_check()
        self.assertNotIn("PRIVATE", json.dumps(report))

    def test_disabled_fabric_plugins_block_skills(self):
        original = self.commands

        def commands(tool, args):
            if tool == "copilot":
                return "ok", [{"name": "fabric-skills", "enabled": False, "version": "0.3.22"}]
            return original(tool, args)

        with patch.object(self, "commands", side_effect=commands):
            self.assertTrue(self.run_check()["blocked"])

    def test_command_failures_never_return_raw_output(self):
        with patch("demo_accelerator.prerequisites.shutil.which", return_value="az"), \
                patch("demo_accelerator.prerequisites.subprocess.run") as run:
            for value in (subprocess.CompletedProcess([], 1, "PRIVATE", "PRIVATE"),
                          subprocess.CompletedProcess([], 0, "PRIVATE", ""),
                          subprocess.TimeoutExpired(["PRIVATE"], 60)):
                if isinstance(value, Exception):
                    run.side_effect = value
                else:
                    run.return_value = value
                self.assertNotIn("PRIVATE", str(command_json("az", ["version"])))

    def test_cli_writes_new_report_and_returns_blocked_exit_status(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            report = {"blocked": True, "checks": []}
            with patch("demo_accelerator.prerequisites.check", return_value=report), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(main(["check-prereqs", "--output", str(output)]), 1)
            self.assertEqual(json.loads(output.read_text()), report)
            from demo_accelerator.cli import execute, parser
            with patch("demo_accelerator.prerequisites.check", return_value=report):
                with self.assertRaises(FileExistsError):
                    execute(parser().parse_args(["check-prereqs", "--output", str(output)]))


if __name__ == "__main__":
    unittest.main()
