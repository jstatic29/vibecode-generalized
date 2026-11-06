import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".github" / "skills" / "fabric-demo-companion"


class CompanionSkillTests(unittest.TestCase):
    def test_entry_point_metadata_and_local_links(self):
        entry = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(entry.startswith("---\nname: fabric-demo-companion\n"))
        self.assertIn("\ndescription: ", entry.split("---", 2)[1])
        self.assertLess(len(entry.splitlines()), 150)
        for path in SKILL.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if "://" not in target and not target.startswith("#"):
                    self.assertTrue((path.parent / target).is_file(), (path, target))

    def test_skill_is_portable_and_does_not_bundle_runtime_state(self):
        for path in SKILL.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.isascii(), path)
                self.assertNotRegex(
                    text, r"(?i)\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b"
                )
                self.assertNotIn("C:\\Users\\", text)
                self.assertNotIn("Bearer ", text)

    def test_agent_checkpoint_sequence_and_evidence_limits(self):
        text = (SKILL / "references" / "ontology-and-agent.md").read_text(encoding="utf-8")
        checkpoints = [
            "1. Create/configure the lakehouse-first draft",
            "2. The operator manually opens errored draft examples",
            "3. With approval, select preview runtime and publish the SQL-only agent.",
            "4. The operator manually adds ontology",
            "5. With approval, publish again in preview runtime.",
        ]
        offsets = [text.index(checkpoint) for checkpoint in checkpoints]
        self.assertEqual(offsets, sorted(offsets))
        for requirement in (
            "not a guaranteed fix",
            "not just entities in a focused ontology projection",
            "not proof that ontology was consulted",
            "post-ontology",
            "Full Fabric IQ acceptance remains incomplete",
            "The output from Fabric data agent should be delivered as-is, without summarizing, rephrasing, or adding extra interpretation.",
        ):
            self.assertIn(requirement, text)

    def test_evidence_template_cannot_claim_completion_by_default(self):
        template = json.loads((SKILL / "templates" / "phase-evidence.json").read_text())
        self.assertFalse(template["approval"]["confirmed"])
        self.assertFalse(template["gate_completion_claimed"])
        self.assertIsNone(template["recorded_at"])
        self.assertEqual(template["checks"][0]["status"], "not_assessed")
        self.assertIsNone(template["checks"][0]["evidence_kind"])
        self.assertTrue(all(value is None for value in template["target"].values()))
        self.assertIn("not CLI gate evidence", template["purpose"])


if __name__ == "__main__":
    unittest.main()
