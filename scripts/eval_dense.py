#!/usr/bin/env python3
"""Measure a contextual embedding model on the fixed weak retrieval set."""

import argparse
import hashlib
import json
from pathlib import Path

import torch
import torch.nn.functional as functional
from transformers import AutoModel, AutoTokenizer

from prepare_training import extract_pair


QUERY_INSTRUCTION = "Given a user task, retrieve the most relevant agent skill"


def load_examples(corpus: Path, split_path: Path) -> tuple[list[str], list[str], list[str], list[str], str]:
    split = json.loads(split_path.read_text())
    digest = hashlib.sha256(corpus.read_bytes()).hexdigest()
    if digest != split["corpus_sha256"]:
        raise ValueError("split manifest does not match corpus")
    test_ids = set(split["splits"]["test"])
    ids, documents, query_ids, queries = [], [], [], []
    with corpus.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            pair = extract_pair(row["skill_md"])
            if pair is None:
                continue
            query, document = pair
            ids.append(row["id"])
            documents.append(document)
            if row["id"] in test_ids:
                query_ids.append(row["id"])
                queries.append(f"Instruct: {QUERY_INSTRUCTION}\nQuery: {query}")
    return ids, documents, query_ids, queries, digest


def encode(model, tokenizer, texts: list[str], batch_size: int, max_length: int) -> torch.Tensor:
    vectors = []
    for offset in range(0, len(texts), batch_size):
        batch = tokenizer(texts[offset:offset + batch_size], padding=True,
                          truncation=True, max_length=max_length, return_tensors="pt")
        batch = {key: value.to(model.device) for key, value in batch.items()}
        with torch.inference_mode():
            states = model(**batch).last_hidden_state
            # Left padding puts the final content token at the last position.
            pooled = states[:, -1]
            vectors.append(functional.normalize(pooled.float(), p=2, dim=1).cpu())
    return torch.cat(vectors)


def evaluate(model_path: str, corpus: Path, split_path: Path, batch_size: int, max_length: int) -> dict:
    ids, documents, query_ids, queries, digest = load_examples(corpus, split_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path, padding_side="left")
    model = AutoModel.from_pretrained(model_path, dtype=torch.bfloat16,
                                     attn_implementation="sdpa").eval().to("cuda")
    docs = encode(model, tokenizer, documents, batch_size, max_length).to("cuda")
    qvec = encode(model, tokenizer, queries, batch_size, max_length).to("cuda")
    ranks = (qvec @ docs.T).topk(10, dim=1).indices.cpu().tolist()
    counts = {1: 0, 5: 0, 10: 0}
    for target, row in zip(query_ids, ranks):
        found = [ids[index] for index in row]
        for k in counts:
            counts[k] += target in found[:k]
    return {
        "model": model_path,
        "corpus_sha256": digest,
        "documents": len(ids),
        "queries": len(queries),
        "max_length": max_length,
        "query_source": "skill frontmatter descriptions (weak labels)",
        **{f"recall_at_{k}": count / len(queries) for k, count in counts.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--corpus", type=Path, default=Path("/data/skills.jsonl"))
    parser.add_argument("--split", type=Path, default=Path("/data/split.json"))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=768)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.model, args.corpus, args.split, args.batch_size, args.max_length)
    encoded = json.dumps(result, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n")
    print(encoded)


if __name__ == "__main__":
    main()
