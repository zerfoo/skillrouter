# Skillrouter Qwen3 0.6B LoRA: experimental v0.1

This is an open-weight **research checkpoint** for selecting agent skills from
task descriptions. It is a LoRA adapter for
[Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
(Apache-2.0). The adapter is released under this repository's Apache-2.0
license. It is not validated for autonomous skill selection or no-match
decisions. Zerfoo's Go retrieval package can use an embedder, but native Go
loading and numerical parity for these weights are still in progress.

## Artifact and inference

The release contains `adapter_model.safetensors` and `adapter_config.json`.
The adapter weight SHA-256 is
`e6c5eef63d363b200a3f0be96d1a832c2a4b8800eb3ebfba3022bf6761e966a8`.
Load the pinned base model revision `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`
with PEFT, then apply the adapter. Query input uses:

```
Instruct: Given a user task, retrieve the most relevant agent skill
Query: <task>
```

Document input is the skill body without YAML frontmatter. Truncate to 768
tokens, pool the final non-padding token, L2-normalize both vectors, and rank
by dot product. The [evaluation script](scripts/eval_dense.py) is the reference
implementation. The adapter was also merged and evaluated as a full model;
merged weights remain private pending a Go parity check.
The packaged adapter and merged model were compared on a sample query in
PyTorch: cosine similarity was 0.999711 and maximum absolute vector difference
was 0.00270. This checks adapter packaging, not Go inference.

## Data and training

- Source: authenticated skills.sh all-time API snapshot on 2026-09-22. Its
  9,829 listings yielded 6,775 retained `SKILL.md` records from 726 GitHub
  repositories with MIT or Apache-2.0 repository licenses.
- Corpus SHA-256: `b89686088e21df7848ab44c7f88bd5bc396cee099fd209f45cf464e63cab293f`.
- Training pairs: 5,363; validation pairs: 677; test queries: 672. Pairs use
  each skill's own frontmatter description as the query and body text as the
  positive document. Sources are disjoint across splits. This is weak
  supervision; task wording was not independently collected.
- Hardware: NVIDIA GB10 on DGX Spark. One epoch of InfoNCE LoRA training,
  72 optimizer steps, batch size 4, gradient accumulation 4, maximum length
  768, learning rate 0.0001, seed 42. Runtime was 9 minutes 48 seconds.
- Software: `ms-swift==4.5.3`, `datasets==4.8.4`, Transformers 5.16.1,
  NVIDIA PyTorch 2.11.0a0+eb65b36914.nv26.02. The exact
  [training script](scripts/train-on-spark.sh) and
  [source list](docs/training-sources-v1.tsv) are public. Raw skill text is not
  included in this release.

## Retrieval on the weak test set

| Retriever | Recall@1 | Recall@5 | Recall@10 |
| --- | ---: | ---: | ---: |
| BM25, skill body | 84.8% | 94.0% | 95.7% |
| Frozen Qwen3-Embedding-0.6B | 71.6% | 87.4% | 90.5% |
| This adapter | 87.5% | 95.4% | 96.7% |

All three scores use the same 672 description-derived test queries against
6,712 eligible skill bodies. The results do not establish performance on
independent user requests. They also do not test abstention, malicious skill
content, or latency in a Go process.

## Known limits and next validation

Descriptions and bodies come from the same authors, so lexical overlap can
inflate every score. The catalog API exposed 9,829 listings, far fewer than
the number shown on the public leaderboard. Repository license checks do not
prove each nested skill has the same license. Before a stable release, build an
independently worded task benchmark with no-match and multi-skill requests,
review source attribution, and verify the merged model's embeddings against a
native Go runtime. The current checkpoint must not be represented as a
production-ready router.
