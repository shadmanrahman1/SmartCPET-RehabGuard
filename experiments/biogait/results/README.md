# BioGait results directory (Sprint B, B15) — data-safety policy.

Generated experiment outputs (JSON/CSV/figures) are written here by the
evaluation tooling under `experiments/biogait/`.

## Policy

- Raw datasets: NEVER commit.
- Raw biomedical video: NEVER commit.
- Local / absolute paths: NEVER commit.
- Participant / patient names: NEVER commit.
- Only neutral, non-identifying aggregate results may be committed, and only
  when they contain no direct identifiers and no restricted raw data.

## What is committed here

- `README.md` — this policy.
- `evaluation_status.json` — statuses only (no measurements of individuals).

## What is git-ignored

Everything else in this directory (numeric results, per-session exports,
figures). These are generated and normally excluded from version control by
`experiments/biogait/results/.gitignore`.
