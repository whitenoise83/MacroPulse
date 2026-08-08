# Phase 2B — Read-only System Health and Freshness Contract

## Scope

Phase 2B observes the persisted governed state of Models 1A, 1B, 1C, and the
Model 1D v0.3.8 prospective shadow. It does not execute a model, refresh data,
resolve an outcome, or write database state.

## Governed run sources

- Model 1A: `forecast_registry`.
- Model 1B: `inflation_live_runs` and `inflation_live_forecasts`.
- Model 1C: `labour_live_runs` and `labour_live_forecasts`.
- Model 1D: `macro_state_shadow_runs` plus outcome rows for read-only status.

The production source models are expected to be version 1.0.0. Model 1D remains
development v0.3.8 research-only.

## Freshness logic

For each latest governed production run, Phase 2B reads the exact persisted
information set that produced that run.

A source series is stale when either:

1. its latest persisted observation is older than the platform-health threshold
   for its frequency; or
2. the stored release calendar contains a release for that source after the
   run's information cutoff and on/before the monitoring date.

Operational health thresholds are:

- daily: 10 days;
- weekly: 21 days;
- monthly: 75 days;
- quarterly: 180 days;
- unknown frequency: 90 days and fail-closed `indeterminate_frequency`.

These are platform-operational thresholds. They do not change a model's data,
equations, estimation, forecast policy, or governance.

Release-calendar coverage is additive evidence. Absence of a calendar row alone
does not mark a source stale; age and metadata checks still apply.

## Model 1D dependency status

A persisted Model 1D shadow run is an immutable prospective observation at its
own information cutoff. Later GDP, inflation, or labour production runs do not
invalidate or rewrite that observation.

Phase 2B reports whether newer source runs exist through
`source_run_advance_detected`, but this is lineage information rather than a
staleness failure. The shadow remains valid when its no-look-ahead flag passes.

A target that has reached its expected availability date but lacks both outcome
rows is reported as `due_for_resolution_attempt`. Phase 2B never resolves it.

## Readiness

`platform_ready_for_downstream` means Models 1A–1C all have successful governed
runs with non-empty persisted information sets and no stale/indeterminate source
series.

Model 1D is reported separately. It does not become production readiness
authority and cannot promote, switch, blend, or replace its frozen source.

## Command

```cmd
python scripts\report_platform_status.py
```

Historical inspection:

```cmd
python scripts\report_platform_status.py --as-of 2026-08-05
```

Machine-readable stdout:

```cmd
python scripts\report_platform_status.py --json
```

The command is read-only and writes no report files.
