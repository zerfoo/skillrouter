# Dataset policy

The collector can select up to 100,000 eligible records from the skills.sh
all-time ranking, in rank order. The authenticated API reported 9,829 total
listings on 2026-09-22, so the reachable corpus is smaller than the configured
ceiling. A record is eligible only when:

- skills.sh marks it as a GitHub source and does not flag it as a duplicate;
- a `SKILL.md` snapshot exists and has nonempty content;
- the source repository's GitHub license endpoint identifies MIT or Apache-2.0;
- its stable skills.sh ID and content hash have not appeared already.

The collector stores ID, source, installs, source license, content hash,
collection time, and `SKILL.md`. Raw training data remains outside Git. A later
run must pin an exact manifest and split by source repository so near-identical
skills from one source cannot leak from training into evaluation. Metadata and
license checks are necessary but do not establish that the content is safe to
execute. Training treats skill text as data, never as instructions.

Before a weight release, publish a model card with corpus counts, excluded
counts by reason, dataset snapshot hash, train/test split IDs, benchmark
results, training recipe, license review, and known failure cases. Do not
claim model quality from training loss alone.
