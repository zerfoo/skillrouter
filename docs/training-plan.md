# Skillrouter training plan

The training target is the user's DGX Spark. The model artifact must be usable
from a Go process through Zerfoo's generic retrieval interface. The skill
corpus, labels, and model weights belong to this repository, not Zerfoo core.

## Candidate and baselines

- Use BM25 and the frozen [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
  encoder as the first measured baselines. Its published weights are Apache-2.0.
- Fine-tune that encoder on the DGX with contrastive query-to-skill pairs only
  after the held-out evaluation set is fixed. Compare a small LoRA run with
  full fine-tuning before choosing the released artifact.
- Add a reranker only if observed top-k errors justify its latency and size.

## Data and evaluation gates

1. Finish a versioned skills.sh snapshot. Record its SHA-256, license counts,
   skipped-record reasons, and the exact API listing count. Keep raw skill text
   out of Git and out of the model repository release.
2. Split by source repository and duplicate content hash. Create task wording
   independently of the `SKILL.md` text for a held-out benchmark; frontmatter
   descriptions alone are weak labels and cannot establish real-world quality.
3. Measure recall@1, recall@5, no-match false positives, and latency against
   both baselines. Inspect failures by skill family and near-duplicate group.
4. Submit a versioned training job to Spark with the base-model revision,
   dataset hash, split manifest, hyperparameters, seed, and output location.
   GPU validation and a native Go parity check are required before release.
5. Publish only when weights, tokenizer, model card, reproducible recipe, and
   a working Zerfoo Go loading example can be released together.

The DGX Spark API was reachable on 2026-09-22. It reported one unallocated GPU
with approximately 122 GB of available GPU memory, but only 1.6 CPU cores
unallocated at that instant. A training pod should request resources through
Spark and wait for capacity rather than bypassing its scheduler.
