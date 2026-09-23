#!/usr/bin/env bash
set -euo pipefail

# Runs inside a DGX Spark GPU pod with the private corpus mounted at /data.
DATA_DIR="${SKILLROUTER_DATA_DIR:-/data}"
OUTPUT_DIR="${SKILLROUTER_OUTPUT_DIR:-/data/outputs/weak-v1}"
EXPECTED_CORPUS_SHA256="b89686088e21df7848ab44c7f88bd5bc396cee099fd209f45cf464e63cab293f"

printf '%s  %s\n' "$EXPECTED_CORPUS_SHA256" "$DATA_DIR/skills.jsonl" | sha256sum -c -
printf '%s  %s\n' "33465ba10b95835ab9954656c89121b30854ce0888aebcfa0c4b92097b4fe1b9" "$DATA_DIR/weak-pairs/train.jsonl" | sha256sum -c -
printf '%s  %s\n' "c9c8b2badf4a5669e2bd42dd1061eb3bc43d853321ee7fc0dbbc0ae07abfc1f7" "$DATA_DIR/weak-pairs/validation.jsonl" | sha256sum -c -
mkdir -p "$OUTPUT_DIR" "$DATA_DIR/cache"
export HF_HOME="$DATA_DIR/cache/huggingface"
export PIP_CACHE_DIR="$DATA_DIR/cache/pip"
export USE_HF=1
export OMP_NUM_THREADS=1

python3 -m pip install 'ms-swift==4.5.3' 'datasets==4.8.4'
python3 - <<'PY' > "$OUTPUT_DIR/environment.json"
import json
from importlib.metadata import version
import torch
print(json.dumps({
    "torch": torch.__version__,
    "transformers": version("transformers"),
    "ms-swift": version("ms-swift"),
    "datasets": version("datasets"),
    "cuda_available": torch.cuda.is_available(),
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
}, sort_keys=True))
PY

TRAIN_DATASET="$DATA_DIR/weak-pairs/train.jsonl"
VAL_DATASET="$DATA_DIR/weak-pairs/validation.jsonl"
EXTRA_ARGS=()
if [[ -n "${SKILLROUTER_SMOKE_SAMPLES:-}" ]]; then
  TRAIN_DATASET="${TRAIN_DATASET}#${SKILLROUTER_SMOKE_SAMPLES}"
  VAL_DATASET="${VAL_DATASET}#16"
  EXTRA_ARGS+=(--max_steps 2)
fi

swift sft \
  --model Qwen/Qwen3-Embedding-0.6B \
  --task_type embedding \
  --model_type qwen3_emb \
  --tuner_type lora \
  --dataset "$TRAIN_DATASET" \
  --val_dataset "$VAL_DATASET" \
  --eval_strategy epoch \
  --save_strategy epoch \
  --output_dir "$OUTPUT_DIR" \
  --num_train_epochs 1 \
  --per_device_train_batch_size 4 \
  --per_device_eval_batch_size 4 \
  --gradient_accumulation_steps 4 \
  --learning_rate 0.0001 \
  --max_length 768 \
  --dataset_num_proc 1 \
  --loss_type infonce \
  --label_names labels \
  --dataloader_drop_last true \
  --logging_steps 25 \
  --seed 42 \
  "${EXTRA_ARGS[@]}"
