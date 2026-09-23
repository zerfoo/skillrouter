import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from summarize import summarize


class SummarizeTests(unittest.TestCase):
    def test_validates_hashes_and_counts_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.jsonl"
            rows = []
            for name, source, content in [("one", "a/repo", "alpha"), ("two", "b/repo", "beta")]:
                rows.append({"id": f"{source}/{name}", "source": source, "license": "MIT",
                             "skill_md": content, "skill_sha256": hashlib.sha256(content.encode()).hexdigest()})
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            result = summarize(path)
            self.assertEqual((result["records"], result["sources"], result["licenses"]),
                             (2, 2, {"MIT": 2}))
            rows[1]["skill_sha256"] = "wrong"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "content hash mismatch"):
                summarize(path)


if __name__ == "__main__":
    unittest.main()
