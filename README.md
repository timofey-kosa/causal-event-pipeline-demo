# Portfolio Methodology Case Study

A compact methodology case study for causal event-data pipelines built from market-data-like asynchronous feeds.

The repository uses synthetic data only. It demonstrates how to build ordered event tapes from asynchronous feeds, isolate pre-event and post-event information, run no-lookahead validation, freeze run artefacts with checksums, and produce an auditable run report.

“This public repository is a sanitised methodology case study. It does not include raw data, venue-specific configuration, execution logic, trained private artefacts, or any operational strategy.”

This demo validates the pipeline structure, not a predictive result. The modelling stage is included as an evaluation scaffold, not as a performance claim. In the public synthetic demo, the baseline is intentionally simple and illustrative.

## What The Demo Shows

- deterministic synthetic feed generation;
- normalised event tape construction;
- ASOF alignment using only past or current observations;
- separate pre-entry and post-entry tapes;
- causal feature generation;
- mechanism-based cohort analysis;
- a V-shaped rebound demonstration on synthetic trajectories;
- an illustrative temporal baseline model scaffold;
- structured JSONL logging;
- hash-based run freezing and a final report.

## Install

For the full demo environment, including tests and LightGBM:

```bash
python -m pip install -e ".[test,lightgbm]"
```

Minimal install without test or optional model extras:

```bash
python -m pip install -e .
```

## Run

```bash
make demo
```

or:

```bash
python -m portfolio_case.cli run --config configs/demo.yaml
```

Each run creates a new directory under:

```text
runs/<run_id>/
```

Expected outputs include logs, frozen manifests, raw/interim/features data, markdown and CSV reports, figures, and a text description of the baseline model scaffold.

## Test

```bash
make test
```

or:

```bash
pytest
```

## Pipeline Diagram

```text
feed_a.parquet       feed_b.parquet
      \                 /
       v               v
        normalised event feeds
                 |
                 v
          unified event tape
                 |
                 v
          ASOF alignment
                 |
        +--------+--------+
        v                 v
 pre-entry tape     post-entry tape
        |                 |
        v                 v
 causal features     trajectories
        \                 /
         v               v
        cohorts -> baseline scaffold -> frozen run report
```

## Pipeline Flow

```text
synthetic feeds
-> normalised event tape
-> ASOF alignment
-> pre-entry tape
-> post-entry tape
-> features
-> cohorts
-> outcomes
-> baseline model scaffold
-> frozen report
```

## Validation Summary

The demo checks schema contracts, timestamp ordering, duplicate event identifiers, ASOF no-lookahead alignment, pre/post separation, temporal train/test splitting, and checksum integrity for key artefacts.

## Resume-Friendly Description

Built a compact Python case study for causal event-data methodology on market-data-like feeds: deterministic synthetic data generation, ordered multi-feed event tapes, no-lookahead feature isolation, validation contracts, structured logging, reproducible run freezing, cohort analysis, and a temporal baseline evaluation scaffold.

## Limitations

This is a simplified public demo. It uses synthetic data only, includes no venue-specific integrations, contains no real thresholds or private features, and is not deployable. The model is illustrative and exists to exercise the evaluation workflow. It is not the central achievement of the repository.
