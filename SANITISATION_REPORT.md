# Sanitisation Report

## Branch Type

`portfolio-methodology-case-study` is intended to be an orphan branch with clean public history.

## Clean-History Confirmation

The branch is created from an empty orphan worktree. No private repository commits are used as ancestors.

## Files Included

- Source package under `src/portfolio_case/`
- Demo configuration under `configs/`
- Unit tests under `tests/`
- Public documentation under `docs/`
- README, packaging metadata, Makefile, requirements, and ignore rules

## Files Intentionally Excluded

- Real raw data
- Real logs
- Real model artefacts
- Private configs
- Local environment files
- External collectors
- Cached experiment outputs
- Private reports
- Machine-specific paths

## Risky Terms Checked

The externally provided disallowed domain and deployment term block was checked during final review. The list itself is not repeated here to avoid reintroducing those strings into the public branch.

## Artefacts Checked

The public source tree is configured to ignore generated runs, parquet files, CSV files, JSONL logs, local databases, local model dumps, and environment files.

## Remaining Concerns

No known private data or private identifiers are intentionally included. Generated demo outputs are synthetic and are ignored by default.

## Public Repository Basis

This branch is designed to be safe as the basis for a separate public repository after the final scan and local commit.
