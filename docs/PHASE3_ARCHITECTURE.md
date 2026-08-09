# Phase III Architecture — Forecast Evaluation & Decision Intelligence

## Purpose

Phase III sits above the released Phase II platform. It evaluates governed
forecast outputs; it does not re-estimate or modify the governed models.

## Separation of responsibilities

### Governed model layer

Owns:

- model specification;
- transformations;
- estimation;
- forecast generation;
- governed prediction persistence;
- model-specific validation and release identity.

### Phase II platform layer

Owns:

- health/freshness;
- orchestration;
- deterministic current-state snapshot;
- integrated read-only platform dashboard;
- release boundary enforcement.

### Phase III evaluation layer

Owns:

- forecast-to-outcome matching;
- outcome-vintage identity;
- deterministic error metrics;
- interval calibration metrics;
- revision histories;
- descriptive release-impact summaries;
- drift/monitoring flags;
- evaluation exports and presentation.

It must not own model selection, production promotion, or parameter updates.

## Evaluation observation identity

The natural evaluation key should be at least:

```text
model_id
model_version
governed_run_id
information_cutoff
target_period
target_variable
outcome_definition
outcome_vintage
```

Resolved observations should also carry:

```text
outcome_value
outcome_availability_date
evaluation_date
forecast_error
```

The precise persistence design belongs to Phase 3B. Phase 3A does not create a
database table.

## Real-time versus revised truth

Macroeconomic data are revised. Phase III therefore cannot treat "actual" as a
single timeless value.

The evaluation service must make outcome-vintage semantics explicit. Where a
first-release value is well-defined, it should be the default for real-time
forecast evaluation. Later revised values may be used for separate analytical
views.

## Model 1D isolation

Model 1D is not folded into the production accuracy scoreboard.

Its prospective observations may be displayed in a distinct research section,
using the existing frozen persistence and outcome-resolution contracts. Phase
III must not use those outcomes to retune or switch the model.

## Presentation

All user-facing evaluation views should be derivable from the same deterministic
evaluation services used by CLI/tests. Streamlit pages should not independently
reimplement metric equations or database matching logic.

## Phase 3A rule

No source-model logic, database schema, forecast persistence, or release tag is
changed during bootstrap.
