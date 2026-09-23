import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from split import make_split


class SplitTests(unittest.TestCase):
    def test_sources_do_not_cross_splits_and_result_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.jsonl"
            rows = [{"id": f"owner/repo{i}/skill{j}", "source": f"owner/repo{i}"}
                    for i in range(12) for j in range(3)]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            result = make_split(path, "test-seed")
            self.assertEqual(result, make_split(path, "test-seed"))
            source_splits = {}
            for split_name, ids in result["splits"].items():
                self.assertTrue(ids)
                for skill_id in ids:
                    source = "/".join(skill_id.split("/")[:2])
                    if source in source_splits:
                        self.assertEqual(source_splits[source], split_name)
                    source_splits[source] = split_name
            self.assertEqual(sum(map(len, result["splits"].values())), len(rows))


if __name__ == "__main__":
    unittest.main()
