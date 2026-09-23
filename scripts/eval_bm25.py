#!/usr/bin/env python3
"""Evaluate lexical retrieval on the source-held-out weak task set."""

import argparse
import hashlib
import json
import math
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from prepare_training import extract_pair


def tokenize(value: str) -> list[str]:
    words = []
    token = []
    for char in value:
        if unicodedata.category(char)[0] in {"L", "N"}:
            token.append(char.lower())
        elif token:
            words.append("".join(token))
            token = []
    if token:
        words.append("".join(token))
    return words


def evaluate(corpus: Path, split_path: Path) -> dict:
    split = json.loads(split_path.read_text())
    digest = hashlib.sha256(corpus.read_bytes()).hexdigest()
    if digest != split["corpus_sha256"]:
        raise ValueError("split manifest does not match corpus")
    test_ids = set(split["splits"]["test"])
    ids = []
    queries = []
    postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
    lengths = []
    with corpus.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            pair = extract_pair(row["skill_md"])
            if pair is None:
                continue
            query, document = pair
            index = len(ids)
            ids.append(row["id"])
            if row["id"] in test_ids:
                queries.append((row["id"], query))
            frequencies = Counter(tokenize(document))
            lengths.append(sum(frequencies.values()))
            for term, count in frequencies.items():
                postings[term].append((index, count))
    mean_length = sum(lengths) / len(lengths)
    hits = {1: 0, 5: 0, 10: 0}
    for target, query in queries:
        scores = defaultdict(float)
        for term in set(tokenize(query)):
            matches = postings.get(term, [])
            if not matches:
                continue
            idf = math.log1p((len(ids) - len(matches) + 0.5) / (len(matches) + 0.5))
            for index, frequency in matches:
                denominator = frequency + 1.2 * (0.25 + 0.75 * lengths[index] / mean_length)
                scores[index] += idf * frequency * 2.2 / denominator
        ranked = sorted(scores, key=lambda index: (-scores[index], ids[index]))[:10]
        found = [ids[index] for index in ranked]
        for k in hits:
            hits[k] += target in found[:k]
    return {
        "corpus_sha256": digest,
        "documents": len(ids),
        "queries": len(queries),
        "recall_at_1": hits[1] / len(queries),
        "recall_at_5": hits[5] / len(queries),
        "recall_at_10": hits[10] / len(queries),
        "query_source": "skill frontmatter descriptions (weak labels)",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/skills.jsonl"))
    parser.add_argument("--split", type=Path, default=Path("data/split.json"))
    args = parser.parse_args()
    print(json.dumps(evaluate(args.corpus, args.split), sort_keys=True))


if __name__ == "__main__":
    main()
