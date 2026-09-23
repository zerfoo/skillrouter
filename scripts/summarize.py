#!/usr/bin/env python3
"""Summarize a local corpus without publishing third-party skill text."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def summarize(path: Path) -> dict:
    digest = hashlib.sha256()
    ids: set[str] = set()
    hashes: set[str] = set()
    licenses: Counter[str] = Counter()
    sources: set[str] = set()
    records = 0
    with path.open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            digest.update(raw)
            row = json.loads(raw)
            skill_id = row["id"]
            content = row["skill_md"]
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            if skill_id in ids or content_hash in hashes:
                raise ValueError(f"duplicate ID or content on line {number}")
            if content_hash != row["skill_sha256"]:
                raise ValueError(f"content hash mismatch on line {number}")
            ids.add(skill_id)
            hashes.add(content_hash)
            sources.add(row["source"])
            licenses[row["license"]] += 1
            records += 1
    return {
        "records": records,
        "sources": len(sources),
        "licenses": dict(sorted(licenses.items())),
        "sha256": digest.hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.corpus), sort_keys=True))


if __name__ == "__main__":
    main()
