#!/usr/bin/env python3
"""Build weak description-to-skill pairs for an initial embedding experiment."""

import argparse
import hashlib
import json
from pathlib import Path

import yaml


def extract_pair(markdown: str) -> tuple[str, str] | None:
    if not markdown.startswith("---\n"):
        return None
    end = markdown.find("\n---", 4)
    if end < 0 or end > 16384:
        return None
    try:
        metadata = yaml.safe_load(markdown[4:end])
    except yaml.YAMLError:
        return None
    if not isinstance(metadata, dict):
        return None
    description = metadata.get("description")
    if not isinstance(description, str):
        return None
    query = " ".join(description.split())[:600]
    body = markdown[end + 4:].strip()[:8000]
    if len(query) < 15 or len(body) < 80:
        return None
    return query, body


def prepare(corpus: Path, split_path: Path, output_dir: Path) -> dict:
    split = json.loads(split_path.read_text())
    digest = hashlib.sha256(corpus.read_bytes()).hexdigest()
    if digest != split["corpus_sha256"]:
        raise ValueError("split manifest does not match corpus")
    assignment = {skill_id: name for name, ids in split["splits"].items() for skill_id in ids}
    if len(assignment) != sum(len(ids) for ids in split["splits"].values()):
        raise ValueError("duplicate skill ID across splits")
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {name: 0 for name in split["splits"]}
    streams = {name: (output_dir / f"{name}.jsonl").open("w", encoding="utf-8") for name in counts}
    try:
        with corpus.open(encoding="utf-8") as source:
            for line in source:
                row = json.loads(line)
                name = assignment.get(row["id"])
                if name is None:
                    raise ValueError(f"unassigned skill ID: {row['id']}")
                pair = extract_pair(row["skill_md"])
                if pair is None:
                    continue
                query, document = pair
                example = {
                    "messages": [{"role": "user", "content": query}],
                    "positive_messages": [[{"role": "user", "content": document}]],
                }
                streams[name].write(json.dumps(example, ensure_ascii=False) + "\n")
                counts[name] += 1
    finally:
        for stream in streams.values():
            stream.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/skills.jsonl"))
    parser.add_argument("--split", type=Path, default=Path("data/split.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/weak-pairs"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.corpus, args.split, args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
