#!/usr/bin/env python3
"""Verify a packaged LoRA adapter matches its merged model on sample inputs."""

import argparse
import json

import torch
import torch.nn.functional as functional
from peft import PeftModel
from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer


def embed(model, tokenizer, text: str) -> torch.Tensor:
    encoded = tokenizer(text, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        states = model(**encoded).last_hidden_state[:, -1].float()
    return functional.normalize(states, dim=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--merged", required=True)
    parser.add_argument("--base", default="Qwen/Qwen3-Embedding-0.6B")
    args = parser.parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.base, padding_side="left")
    base = AutoModelForCausalLM.from_pretrained(args.base, dtype=torch.bfloat16,
                                               attn_implementation="sdpa").eval().to("cuda")
    adapter = PeftModel.from_pretrained(base, args.adapter).eval()
    merged = AutoModel.from_pretrained(args.merged, dtype=torch.bfloat16,
                                      attn_implementation="sdpa").eval().to("cuda")
    text = "Instruct: Given a user task, retrieve the most relevant agent skill\nQuery: Build a responsive web page"
    adapter_vector = embed(adapter.base_model.model.model, tokenizer, text)
    merged_vector = embed(merged, tokenizer, text)
    result = {
        "cosine": float((adapter_vector * merged_vector).sum()),
        "max_abs_difference": float((adapter_vector - merged_vector).abs().max()),
    }
    print(json.dumps(result, sort_keys=True))
    if result["cosine"] < 0.999 or result["max_abs_difference"] > 0.01:
        raise SystemExit("adapter and merged model differ beyond tolerance")


if __name__ == "__main__":
    main()
