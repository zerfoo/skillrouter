import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from eval_bm25 import evaluate, tokenize


class BM25EvaluationTests(unittest.TestCase):
    def test_unicode_tokenization_matches_word_boundaries(self):
        self.assertEqual(tokenize("Café_API 42"), ["café", "api", "42"])

    def test_retrieves_distinct_held_out_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus.jsonl"
            body = "Use a specific method to manage deployments reliably. " * 3
            rows = [
                {"id": "a/r/one", "skill_md": "---\ndescription: Manage deployments reliably\n---\n" + body},
                {"id": "b/r/two", "skill_md": "---\ndescription: Analyze database tables\n---\n" + "Analyze database tables and indexes carefully. " * 3},
            ]
            corpus.write_text("".join(json.dumps(row) + "\n" for row in rows))
            split = root / "split.json"
            split.write_text(json.dumps({"corpus_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
                                         "splits": {"train": ["b/r/two"], "test": ["a/r/one"]}}))
            result = evaluate(corpus, split)
            self.assertEqual((result["documents"], result["queries"], result["recall_at_1"]), (2, 1, 1.0))


if __name__ == "__main__":
    unittest.main()
