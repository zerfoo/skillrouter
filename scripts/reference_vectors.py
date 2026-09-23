#!/usr/bin/env python3
"""Freeze task and document vectors for Go inference parity checks."""

import argparse
import json

import torch
import torch.nn.functional as functional
from transformers import AutoModel, AutoTokenizer


QUERY_INSTRUCTION = "Instruct: Given a user task, retrieve the most relevant agent skill\nQuery: "
QUERIES = [
    "Create a Go HTTP server",
    "Audit a web app for security vulnerabilities",
    "Generate a bar chart from a spreadsheet",
    "Design a mobile onboarding screen",
]
DOCUMENTS = [
    "Create a Go HTTP server with routing and middleware",
    "Review web application security and identify vulnerabilities",
    "Read spreadsheet data and produce a bar chart",
    "Design a polished mobile onboarding user interface",
    "Write marketing copy for a landing page",
    "Deploy a Python service to AWS",
    "Summarize a research paper",
    "Build a Godot game level",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    examples = [("probe", "hello world")]
    examples += [("query", QUERY_INSTRUCTION + text) for text in QUERIES]
    examples += [("document", text) for text in DOCUMENTS]

    tokenizer = AutoTokenizer.from_pretrained(args.model, padding_side="left")
    model = AutoModel.from_pretrained(
        args.model, dtype=torch.bfloat16, attn_implementation="sdpa"
    ).eval().to("cuda")
    rows = []
    for role, text in examples:
        batch = tokenizer(text, truncation=True, max_length=768, return_tensors="pt")
        token_ids = batch["input_ids"][0].tolist()
        batch = {key: value.to("cuda") for key, value in batch.items()}
        with torch.inference_mode():
            states = model(**batch).last_hidden_state
            vector = functional.normalize(states[:, -1].float(), p=2, dim=1)[0]
        rows.append({
            "role": role,
            "text": text,
            "token_ids": token_ids,
            "vector": vector.cpu().tolist(),
        })

    queries = torch.tensor([row["vector"] for row in rows if row["role"] == "query"])
    documents = torch.tensor([row["vector"] for row in rows if row["role"] == "document"])
    ranks = torch.argsort(queries @ documents.T, dim=1, descending=True).tolist()
    result = {
        "model": "skillrouter-merged-weak-v1",
        "max_length": 768,
        "rows": rows,
        "reference_ranks": ranks,
    }
    with open(args.output, "w", encoding="utf-8") as output:
        json.dump(result, output)
    print(json.dumps({
        "rows": len(rows),
        "dims": [len(row["vector"]) for row in rows],
        "token_counts": [len(row["token_ids"]) for row in rows],
        "ranks": ranks,
    }))


if __name__ == "__main__":
    main()
