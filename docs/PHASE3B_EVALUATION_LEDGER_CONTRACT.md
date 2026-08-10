# Phase 3B — Production Forecast Evaluation Ledger Contract

## Status

Phase 3B implementation contract.

This workstream evaluates persisted governed production forecasts from Models
1A, 1B, and 1C. It does not evaluate Model 1D as a production model.

## 1. Scope

The Phase 3B service is read-only and in-memory.

It reads:

- `forecast_registry`;
- `inflation_live_runs`;
- `inflation_live_forecasts`;
- `labour_live_runs`;
- `labour_live_forecasts`;
- explicit `observations` rows whose `vintage_type = 'initial'`, used to
  identify the target period's initial release date;
- the exact cached ALFRED/FRED historical snapshot for that release date, used
  to reconstruct the target value exactly as it was known on release day.

It does not:

- initialise or migrate the database;
- download data;
- create an evaluation table;
- update any governed forecast;
- update any outcome;
- write reports to the repository;
- invoke Models 1A–1D;
- invoke platform orchestration;
- use Model 1D outcomes.

A persisted evaluation store, if justified later, must be separately governed
and append-only.

## 2. Production identities

Only these governed production identities are eligible:

| Component | Model | Version |
| --- | --- | --- |
| 1A | `US_GDP_NOWCAST_1A` | `1.0.0` |
| 1B | `US_INFLATION_NOWCAST_1B` | `1.0.0` |
| 1C | `US_LABOUR_NOWCAST_1C` | `1.0.0` |

Unknown lifecycle/version identities fail closed.

## 3. Outcome contract

Phase 3B v1 supports one outcome vintage:

```text
first_release
```

Outcome definition:

```text
initial_release_transformed_target
```

The initial-vintage observation identifies the target release date. The
outcome itself is reconstructed from the complete historical snapshot as of
that release date and then transformed with the governed target
transformation.

This distinction matters for transformed targets such as payroll change,
inflation, and GDP growth because the previous period may have been revised by
the time the target period is released. Differencing each period's independent
initial level would not reproduce the information set actually published on
the target release day.

Examples:

- GDP: annualised quarter-on-quarter log growth of `GDPC1`;
- CPI/PCE targets: annualised month-on-month log inflation;
- payrolls: monthly level difference;
- unemployment: monthly level;
- average hourly earnings: annualised month-on-month log growth.

Current revised values are never silently substituted for first-release
outcomes.

## 4. Availability and no-look-ahead

A forecast may be scored only when:

1. an explicit initial-vintage target observation is locally recorded;
2. its `realtime_start` is on or before the evaluation `as_of`;
3. the forecast information cutoff is strictly before that release date;
4. the exact historical snapshot for that release date is cached;
5. the governed target transform can be reconstructed from that snapshot;
6. the transformed target value is finite.

When no target initial vintage exists, Phase 3B distinguishes a future/incomplete
target from a target whose expected release has passed but whose initial-vintage
evidence has not yet been ingested. Neither state is scored.

Because forecast cutoffs and release availability are date-granular, a cutoff
on the release date itself fails closed. The ledger cannot prove intraday
ordering.

## 5. Resolution states

Expected states include:

- `resolved`;
- `unresolved_outcome_not_yet_available`;
- `unresolved_initial_vintage_not_ingested`;
- `unresolved_release_snapshot_not_cached`;
- `unresolved_outcome_transform_error`;
- `structurally_unavailable`;
- `invalid_missing_information_cutoff`;
- `invalid_missing_forecast_value`;
- `invalid_no_look_ahead`.

Unresolved rows are retained as evidence. They are not dropped merely because
they cannot yet be scored.

## 6. Error convention

Phase III canonical signed error is:

```text
signed_error = forecast_value - outcome_value
```

Therefore:

- positive signed error = overprediction;
- negative signed error = underprediction.

The ledger also records absolute and squared error. Phase 3C will aggregate
these into accuracy/calibration metrics.

## 7. Interval evidence

For resolved observations with finite lower and upper 80% bounds:

```text
interval_covered = lower_80 <= outcome_value <= upper_80
```

Interval width is recorded independently of outcome resolution.

## 8. Identity

`forecast_identity` hashes:

```text
model_id | model_version | run_id | target_series | target_period
```

`evaluation_id` additionally includes:

```text
outcome_vintage | evaluation_as_of
```

This separates a stable governed forecast identity from a deterministic
evaluation snapshot identity.

## 9. Determinism

For the same:

- persisted governed forecast state;
- vintage metadata;
- cached historical snapshots;
- Phase III contract;
- evaluation `as_of`;

the ledger must produce identical semantic rows.

No wall-clock timestamp is included in the ledger.

## 10. CLI

Read-only summary:

```cmd
python scripts\report_forecast_evaluation.py
```

Historical view:

```cmd
python scripts\report_forecast_evaluation.py --as-of YYYY-MM-DD
```

JSON:

```cmd
python scripts\report_forecast_evaluation.py --json
```

Component filter:

```cmd
python scripts\report_forecast_evaluation.py --component 1B
```

The CLI does not create an output file.

## 11. Phase boundary

Phase 3B is an evidence service, not an adaptive control loop.

Its results must not automatically:

- change model parameters;
- switch production candidates;
- alter interval methods;
- modify production lifecycle;
- promote Model 1D;
- trigger backfills.


## 12. Initial-vintage evidence freshness

Phase 3B evaluation remains read-only, but its declared outcome evidence must
be refreshed by the existing data-ingestion layer.

Existing repository commands provide that evidence:

```cmd
python scripts\download_fred_data.py
python scripts\download_inflation_initial_targets.py
python scripts\download_labour_initial_targets.py
```

For the baseline downloader, omitting `--skip-initial` is intentional when
refreshing evaluation evidence.

These commands update source observations only. They do not alter persisted
governed forecasts or Model 1D prospective predictions.

A production forecast whose target release is due but whose initial vintage has
not been refreshed remains:

```text
unresolved_initial_vintage_not_ingested
```

Phase 3B never falls back to a `latest` value to make that row scoreable.


## 13. Release-date snapshot semantics

Phase 3B follows the same realised-outcome semantics already used by the
governed pseudo-real-time backtests:

```text
target initial vintage
        -> identifies target release date
exact ALFRED/FRED snapshot on that date
        -> reconstructs the full release-day target information
governed transform
        -> realised evaluation target
```

The source-ingestion command is:

```cmd
python scripts\refresh_phase3_outcome_snapshots.py --as-of YYYY-MM-DD
```

This command may write only to the existing historical-snapshot source-evidence
store. It must not execute or alter Models 1A–1D or mutate governed forecasts.

Existing cached snapshots are left unchanged unless `--refresh` is explicitly
supplied.
