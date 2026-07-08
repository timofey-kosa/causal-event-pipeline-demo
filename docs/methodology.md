# Methodology

This case study demonstrates a small causal event-response workflow using synthetic, market-data-like event feeds only.

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

## Event Tapes

Two asynchronous feeds are generated with deterministic random seeds. Each feed has timestamps, event identifiers, source labels, observed values, noise, and synthetic disturbance markers.

The feeds are normalised into a shared schema and combined into one chronological event tape. The tape is the canonical ordered view used by later stages.

## ASOF Alignment

The alignment step attaches the latest known observation from the other feed at or before each event timestamp. This mirrors a time-aware view: a row can only use information that would already have been observable at that moment.

## Pre-Entry And Post-Entry Separation

Pre-entry rows are strictly before the synthetic event timestamp. They are used for feature generation.

Post-entry rows start at or after the synthetic event timestamp. They are used for trajectory and downstream outcome analysis.

This separation matters because feature columns should describe what was knowable before the event, while outcome columns describe what happened afterward. Mixing the two creates future leakage and makes evaluation unreliable.

## Cohorts And Outcomes

Synthetic episodes are grouped into mechanism-based cohorts. The cohort analysis compares downstream trajectories and summary outcomes across those groups. One cohort is constructed to show a V-shaped rebound pattern so the plotting and reporting flow has an interpretable signal to inspect.

## Baseline Model

The baseline model uses only pre-entry feature columns and a temporal train/test split. It is an evaluation scaffold: the point is to demonstrate a reproducible validation path, not to claim predictive performance or deployment readiness.
