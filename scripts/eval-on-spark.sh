#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${SKILLROUTER_DATA_DIR:-/data}"
OUTPUT_DIR="$DATA_DIR/outputs/evaluation-v1"
mkdir -p "$OUTPUT_DIR" "$DATA_DIR/cache"
export HF_HOME="$DATA_DIR/cache/huggingface"
export PIP_CACHE_DIR="$DATA_DIR/cache/pip"
export USE_HF=1
export OMP_NUM_THREADS=1

printf '%s  %s\n' 'b89686088e21df7848ab44c7f88bd5bc396cee099fd209f45cf464e63cab293f' "$DATA_DIR/skills.jsonl" | sha256sum -c -
python3 -m pip install 'ms-swift==4.5.3' 'datasets==4.8.4'

CHECKPOINT="$(find "$DATA_DIR/outputs/weak-v1" -type d -name 'checkpoint-*' | sort -V | tail -1)"
if [[ -z "$CHECKPOINT" ]]; then
  echo 'no training checkpoint found' >&2
  exit 1
fi
printf '%s\n' "$CHECKPOINT" > "$OUTPUT_DIR/checkpoint.txt"

swift export --adapters "$CHECKPOINT" --merge_lora true --output_dir "$OUTPUT_DIR/merged"
python3 "$DATA_DIR/eval_dense.py" \
  --model Qwen/Qwen3-Embedding-0.6B \
  --output "$OUTPUT_DIR/frozen.json"
python3 "$DATA_DIR/eval_dense.py" \
  --model "$OUTPUT_DIR/merged" \
  --output "$OUTPUT_DIR/finetuned.json"
