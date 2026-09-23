# Skillrouter

Skillrouter is the open-weights skill-selection model built with Zerfoo. Its
model, data recipes, and evaluation live here; Zerfoo itself keeps the encoder,
training loss, and retrieval APIs generic for other Go applications.

## Status

**The first corpus snapshot and an experimental open-weight adapter are
available.** [v0.1.0-experimental](https://github.com/zerfoo/skillrouter/releases/tag/v0.1.0-experimental)
contains a Qwen3-Embedding-0.6B LoRA adapter. Its
[model card](MODEL_CARD.md) reports a weak-label benchmark and the remaining
validation needed before stable use. On 2026-09-22, the authenticated skills.sh API
reported 9,829 listings. License, duplicate, and content checks retained 6,775
skills from 726 repositories. The [snapshot manifest](docs/snapshot-2026-09-22.json)
records the corpus hash, license totals, and source-disjoint split counts.
The larger number displayed on the public leaderboard is not the API's
paginated listing count.

The documented skills.sh catalog API requires a Vercel OIDC token. The local
Vercel project link supplies one through an ignored `.env.local` file. The
collector also requires a GitHub token to verify source repository licenses.
See [dataset policy](docs/dataset-policy.md).

## Intended system

1. Build a reproducible corpus snapshot of licensed `SKILL.md` files.
2. Create task-to-skill relevance labels, including hard negatives, multi-skill
   requests, and requests for which no skill should be chosen.
3. Establish BM25 and pretrained-encoder baselines on held-out sources.
4. Train a contextual bi-encoder with Zerfoo's generic contrastive training
   primitives. Add a reranker only if measured retrieval errors justify it.
5. Publish versioned weights, tokenizer, model card, evaluation report, and a
   small Go example that loads the artifact through Zerfoo.

The agent-facing "one skill" is a discovery instruction that calls search and
fetch. It is not baked into Zerfoo's generic package.

## Native Go inference parity

The [frozen reference fixture](tests/fixtures/reference-vectors-weak-v1.json)
contains exact token IDs and normalized vectors for one probe, four task queries,
and eight candidate descriptions. It was generated on DGX Spark from the merged
BF16 experimental checkpoint with
[`scripts/reference_vectors.py`](scripts/reference_vectors.py). The fixture is
for numerical interoperability; its short, hand-written strings do not measure
retrieval quality on the skills.sh catalog.

Zerfoo's contextual GGUF loader now accepts the official Qwen3-Embedding-0.6B
F16 GGUF plus a GGUF conversion of the released PEFT adapter. The CPU parity
run matched all 13 token sequences, achieved minimum vector cosine 0.9998455
and maximum component error 0.0030001, and matched the top document for all
four queries. Minor lower-rank differences remain. The reference and runtime
use BF16 and F16 base weights respectively, so exact vector equality is not
expected. The [Go implementation plan](https://github.com/zerfoo/zerfoo/blob/feat/contextual-embedding-go/docs/plan-contextual-embedding-go.md)
tracks GPU parity and native training separately.

Reproduce with the pinned official GGUF and the released adapter:

```sh
go run ./cmd/convert-peft-adapter -help
go run ./cmd/embedding-parity -help
```

These commands are in Zerfoo; use the converter to produce a GGUF adapter and
then give the parity command the base GGUF, adapter GGUF, and fixture paths.
SHA-256: base F16 GGUF `421a27e58d165478cc7acb984a688c2aa41404968b0203e7cd743ece44c54340`;
converted GGUF adapter `83bcde11f2e38d1c1be9ea60e8ae92a7e90d5d32322370ff5ad92ea7b3422cb7`;
reference fixture `13ed3b0e81baea9c880a2da915760487fc748c639f33e1c6818df86b064881e2`.

## Link a Vercel project

From this repository, link an existing Vercel project that has OIDC federation
enabled under **Settings → Security**. The link is local and ignored by Git:

```sh
npx vercel link
npx vercel env pull .env.local
```

The collector reads the ignored `.env.local` token automatically. It uses
`GITHUB_TOKEN` or the local `gh` login for source license checks. Do not paste
credentials into chat or commit `.env.local`. A long collection may outlast a
static token; the collector is resumable and can be restarted after refreshing
the token.

## Collecting a snapshot

```sh
python3 scripts/collect.py --limit 100000 --output data/skills.jsonl
python3 scripts/summarize.py data/skills.jsonl
python3 scripts/split.py data/skills.jsonl
python3 scripts/prepare_training.py
python3 scripts/eval_bm25.py
```

Collection is resumable. It stores records only for GitHub sources with an
explicit MIT or Apache-2.0 repository license, a non-duplicate skills.sh ID,
and a nonempty `SKILL.md` snapshot. The corpus file is ignored by Git and must
be reviewed before any redistribution. Collection is not training.

`prepare_training.py` creates weak description-to-body pairs for an initial
experiment. These descriptions come from the skills themselves; evaluation on
those pairs must not be presented as performance on independent user requests.
The [first lexical baseline](docs/baseline-weak-2026-09-22.json) measures this
weak set only.
