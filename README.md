# Skillrouter

Skillrouter is the open-weights skill-selection model built with Zerfoo. Its
model, data recipes, and evaluation live here; Zerfoo itself keeps the encoder,
training loss, and retrieval APIs generic for other Go applications.

## Status

**Model training has not run yet. No weights have been released.** The first
target is the available skills.sh all-time catalog, selected by install rank.
On 2026-09-22, the authenticated paginated API reported 9,829 listings; this
is the upper bound for this collection path, before license and content filters.
The much larger number displayed on the public leaderboard is not the API's
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
```

Collection is resumable. It stores records only for GitHub sources with an
explicit MIT or Apache-2.0 repository license, a non-duplicate skills.sh ID,
and a nonempty `SKILL.md` snapshot. The corpus file is ignored by Git and must
be reviewed before any redistribution. Collection is not training.
