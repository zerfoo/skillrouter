import sys
import tempfile
import json
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collect import eligible_listing, existing_keys, skill_markdown


class CollectorSelectionTests(unittest.TestCase):
    def test_selects_github_nonduplicate_with_stable_id(self):
        row = {"id": "owner/repo/example", "source": "owner/repo", "sourceType": "github"}
        self.assertTrue(eligible_listing(row))
        self.assertFalse(eligible_listing({**row, "isDuplicate": True}))
        self.assertFalse(eligible_listing({**row, "sourceType": "well-known"}))
        self.assertFalse(eligible_listing({**row, "id": "wrong/repo/example"}))

    def test_resume_loads_ids_and_content_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "skills.jsonl"
            path.write_text(json.dumps({"id": "owner/repo/skill", "skill_sha256": "abc"}) + "\n")
            self.assertEqual(existing_keys(path), ({"owner/repo/skill"}, {"abc"}))

    def test_extracts_only_nonempty_root_skill_markdown(self):
        self.assertEqual(skill_markdown({"files": [{"path": "SKILL.md", "contents": "  instructions  "}]}), "instructions")
        self.assertIsNone(skill_markdown({"files": [{"path": "notes/SKILL.md", "contents": "wrong"}]}))
        self.assertIsNone(skill_markdown({"files": None}))


if __name__ == "__main__":
    unittest.main()
