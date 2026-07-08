# Validation

The demo includes validation checks for the engineering claims it makes.

## Schema Checks

Schema checks confirm that each feed contains the required columns before later stages depend on them. This catches accidental source changes early.

## Timestamp Checks

Timestamp checks verify that each source is ordered over time and has no null timestamps. Ordered timestamps are required for event tapes, ASOF alignment, and temporal evaluation.

## Duplicate Checks

Duplicate event identifiers are rejected. Duplicates can create repeated evidence, distort row counts, and make artefact audits harder to trust.

## ASOF No-Lookahead Check

The ASOF check confirms that the aligned observation from the other feed never occurs after the current row timestamp. This protects the pipeline from future leakage during cross-feed alignment.

## Pre/Post Separation Check

Pre-entry rows must be strictly before the event timestamp. Post-entry rows must start at or after it and have non-negative elapsed time. The feature table is also checked so post-entry outcome columns are not used as model features.

## Temporal Train/Test Split

The baseline model uses earlier episodes for training and later episodes for testing. This avoids random shuffling across time, which can overstate performance in event-response settings.

## Checksum Freeze

The freeze step writes a manifest, config snapshot, and SHA-256 checksums for key outputs. This gives each run an auditable record and makes accidental artefact mutation visible.
