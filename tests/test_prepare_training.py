import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_training import extract_pair, prepare


class PrepareTrainingTests(unittest.TestCase):
    def test_extracts_description_without_copying_it_into_document(self):
        text = "---\ndescription: Design a responsive interface for a web app\n---\n" + "Use a visual grid. " * 8
        query, document = extract_pair(text)
        self.assertEqual(query, "Design a responsive interface for a web app")
        self.assertNotIn("description:", document)

    def test_rejects_mismatched_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus.jsonl"
            corpus.write_text(json.dumps({"id": "a/b/c", "skill_md": "text"}) + "\n")
            split = root / "split.json"
            split.write_text(json.dumps({"corpus_sha256": "wrong", "splits": {"train": ["a/b/c"]}}))
            with self.assertRaisesRegex(ValueError, "does not match"):
                prepare(corpus, split, root / "out")
            split.write_text(json.dumps({"corpus_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
                                         "splits": {"train": ["a/b/c"]}}))
            self.assertEqual(prepare(corpus, split, root / "out"), {"train": 0})


if __name__ == "__main__":
    unittest.main()
