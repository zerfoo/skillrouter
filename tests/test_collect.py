import sys
import tempfile
import json
from unittest.mock import patch
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collect import HTTPStatusError, ResponseTooLarge, collect, eligible_listing, existing_keys, fetch_skill, load_oidc_token, skill_markdown


class CollectorSelectionTests(unittest.TestCase):
    def test_selects_github_nonduplicate_with_stable_id(self):
        row = {"id": "owner/repo/example", "source": "owner/repo", "sourceType": "github"}
        self.assertTrue(eligible_listing(row))
        self.assertFalse(eligible_listing({**row, "isDuplicate": True}))
        self.assertFalse(eligible_listing({**row, "sourceType": "well-known"}))
        self.assertFalse(eligible_listing({**row, "id": "wrong/repo/example"}))

    def test_reads_local_oidc_without_exposing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.local"
            path.write_text('VERCEL_OIDC_TOKEN="sample.jwt.value"\n')
            self.assertEqual(load_oidc_token(path), "sample.jwt.value")

    def test_resume_loads_ids_and_content_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "skills.jsonl"
            path.write_text(json.dumps({"id": "owner/repo/skill", "skill_sha256": "abc"}) + "\n")
            self.assertEqual(existing_keys(path), ({"owner/repo/skill"}, {"abc"}))

    def test_collection_filters_license_and_duplicate_content(self):
        rows = [
            {"id": "a/repo/one", "source": "a/repo", "sourceType": "github", "name": "one", "installs": 10},
            {"id": "a/repo/copy", "source": "a/repo", "sourceType": "github", "name": "copy", "installs": 9},
            {"id": "b/repo/two", "source": "b/repo", "sourceType": "github", "name": "two", "installs": 8},
        ]
        def fake_get(url, token, *, github=False):
            if "page=0" in url:
                return {"data": rows, "pagination": {"total": 3, "hasMore": False}}
            if url.endswith("a/repo/license"):
                return {"license": {"spdx_id": "MIT"}}
            if url.endswith("b/repo/license"):
                return {"license": {"spdx_id": "GPL-3.0"}}
            if url.endswith("a/repo/one") or url.endswith("a/repo/copy"):
                return {"files": [{"path": "SKILL.md", "contents": "same content"}]}
            raise AssertionError(url)
        with tempfile.TemporaryDirectory() as directory, patch("collect.get_json", side_effect=fake_get):
            path = Path(directory) / "skills.jsonl"
            collect(10, path, "sample-token", "sample-github-token")
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([item["id"] for item in records], ["a/repo/one"])
            self.assertEqual(records[0]["license"], "MIT")

    def test_extracts_only_nonempty_root_skill_markdown(self):
        self.assertEqual(skill_markdown({"files": [{"path": "SKILL.md", "contents": "  instructions  "}]}), "instructions")
        self.assertIsNone(skill_markdown({"files": [{"path": "notes/SKILL.md", "contents": "wrong"}]}))
        self.assertIsNone(skill_markdown({"files": None}))

    def test_oversized_detail_does_not_abort_collection(self):
        item = {"id": "owner/repo/large"}
        with patch("collect.get_json", side_effect=ResponseTooLarge("oversized")), patch("collect.time.sleep"):
            self.assertEqual(fetch_skill(item, "sample-token"), (item, None))

    def test_bad_detail_request_is_skipped_but_auth_error_is_fatal(self):
        item = {"id": "owner/repo/bad"}
        with patch("collect.time.sleep"), patch("collect.get_json", side_effect=HTTPStatusError(400, "url")):
            self.assertEqual(fetch_skill(item, "sample-token"), (item, None))
        with patch("collect.time.sleep"), patch("collect.get_json", side_effect=HTTPStatusError(401, "url")):
            with self.assertRaises(HTTPStatusError):
                fetch_skill(item, "sample-token")


if __name__ == "__main__":
    unittest.main()
