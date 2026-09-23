#!/usr/bin/env python3
"""Create a deterministic source-disjoint corpus split manifest."""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def make_split(path: Path, seed: str) -> dict:
    by_source: dict[str, list[str]] = defaultdict(list)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for raw in stream:
            digest.update(raw)
            row = json.loads(raw)
            by_source[row["source"]].append(row["id"])
    if len(by_source) < 3:
        raise ValueError("at least three source repositories are required")
    groups = sorted(by_source.items(), key=lambda entry: (
        -len(entry[1]), hashlib.sha256(f"{seed}:{entry[0]}".encode()).hexdigest()))
    total = sum(len(ids) for ids in by_source.values())
    targets = {"train": total * 0.8, "validation": total * 0.1, "test": total * 0.1}
    splits: dict[str, list[str]] = {name: [] for name in targets}
    for _source, ids in groups:
        name = max(targets, key=lambda part: (
            (targets[part] - len(splits[part])) / targets[part],
            -list(targets).index(part)))
        splits[name].extend(ids)
    return {
        "corpus_sha256": digest.hexdigest(),
        "seed": seed,
        "splits": {name: sorted(ids) for name, ids in splits.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--seed", default="skillrouter-v1")
    parser.add_argument("--output", type=Path, default=Path("data/split.json"))
    args = parser.parse_args()
    result = make_split(args.corpus, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"corpus_sha256": result["corpus_sha256"],
                      "counts": {name: len(ids) for name, ids in result["splits"].items()},
                      "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
