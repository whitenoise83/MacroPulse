# Phase 3C — Accuracy, Calibration & Drift Monitoring Contract

## Status

Phase 3C implementation contract.

Phase 3C consumes the governed Phase 3B forecast-evaluation ledger. It does not
reconstruct realised outcomes independently and does not alter Models 1A–1D.

## 1. Scope

Phase 3C is read-only and in-memory.

It provides:

- target-series accuracy metrics;
- 80% interval calibration evidence;
- interval-width evidence;
- directional accuracy where the governed target transform represents a
  change rather than a level;
- forecast-stage breakdowns;
- forecast-horizon breakdowns;
- descriptive recent-versus-reference drift evidence;
- deterministic JSON/text reporting.

It does not:

- write an evaluation table;
- download or refresh source data;
- initialise or migrate the database;
- modify a governed forecast;
- change model parameters;
- switch production candidates;
- promote/demote a model;
- evaluate Model 1D as a production model;
- use monitoring evidence for automatic adaptation.

## 2. Canonical observation set

Only Phase 3B rows satisfying both:

```text
evaluation_status == "resolved"
no_look_ahead_pass == True
```

are eligible for performance metrics.

Unresolved, structural, and invalid rows remain part of the Phase 3B evidence
ledger but are not silently included in accuracy statistics.

## 3. No cross-target raw-error pooling

Raw forecast errors are meaningful only within a target's units.

Therefore MAE, RMSE, bias, and median absolute error are computed at:

```text
component + target_series
```

and never pooled across target series.

This prevents invalid aggregation such as combining:

- payroll errors measured in thousands of jobs;
- unemployment errors measured in percentage points;
- earnings-growth errors measured in annualised percentage rates.

Component-level counts may be displayed, but Phase 3C does not create a
cross-target raw-error score.

## 4. Accuracy metrics

For each governed target series:

```text
MAE  = mean(abs(forecast - outcome))
RMSE = sqrt(mean((forecast - outcome)^2))
Bias = mean(forecast - outcome)
Median absolute error = median(abs(forecast - outcome))
```

Positive bias means systematic overprediction under the Phase 3B error
convention.

## 5. Calibration evidence

Where finite 80% intervals exist:

```text
interval_coverage_80
coverage_gap_vs_nominal_80 = interval_coverage_80 - 0.80
mean_interval_width
median_interval_width
```

Coverage is descriptive empirical evidence. It is not a statistical
calibration test by itself.

## 6. Directional accuracy

Directional accuracy is computed only when the governed target transformation
is not `level`.

For those targets:

```text
direction_correct =
    sign(forecast_value) == sign(outcome_value)
```

A level target such as unemployment does not receive this metric because the
sign of its level is not economically meaningful as a forecast direction.

## 7. Sample-size flag

Phase 3C computes descriptive statistics whenever resolved observations exist,
but marks a target/group:

```text
insufficient_for_interpretation
```

until it has at least:

```text
8 resolved forecast observations
```

At 8 or more:

```text
descriptive_ready
```

This threshold is an operational interpretation guard, not a statistical
significance threshold.

Current Phase 3B evidence may therefore produce valid numerical metrics while
still being explicitly marked insufficient.

## 8. Forecast-stage breakdown

The same target-specific metrics may be grouped by:

```text
forecast_stage
```

Missing stages become `UNKNOWN`.

Stage metrics are never pooled across target series.

## 9. Forecast-horizon breakdown

Phase 3C derives deterministic release lead-time buckets from Phase 3B
`lead_days`:

```text
0-7d
8-14d
15-30d
31-60d
61+d
UNKNOWN
```

A negative lead is labelled `INVALID_NEGATIVE`; valid Phase 3B resolved rows
should not normally reach that state.

## 10. Drift evidence

Drift is descriptive, not an automated alert.

For each target series independently, once at least 12 resolved forecast
observations exist:

```text
recent window    = latest 4 resolved forecasts
reference window = preceding 8 resolved forecasts
```

Phase 3C reports:

```text
recent MAE
reference MAE
recent/reference MAE ratio
recent bias
reference bias
bias shift
recent 80% coverage
reference 80% coverage
coverage shift
```

Before 12 observations:

```text
drift_status = insufficient_sample
```

At 12 or more:

```text
drift_status = descriptive_available
```

Phase 3C deliberately does not classify a ratio or shift as good, bad,
warning, critical, promotion-worthy, or demotion-worthy.

## 11. Determinism

For the same:

- Phase 3B ledger;
- evaluation `as_of`;
- Phase 3C contract;

the semantic report is deterministic.

No wall-clock timestamp is part of the report.

## 12. CLI

Current report:

```cmd
python scripts\report_forecast_performance.py
```

Historical report:

```cmd
python scripts\report_forecast_performance.py --as-of YYYY-MM-DD
```

Detailed stage/horizon breakdowns:

```cmd
python scripts\report_forecast_performance.py --breakdowns
```

Deterministic JSON:

```cmd
python scripts\report_forecast_performance.py --json
```

Optional filters:

```cmd
python scripts\report_forecast_performance.py --component 1C
python scripts\report_forecast_performance.py --target-series PAYEMS
```

The CLI writes no report file.

## 13. Model 1D boundary

Model 1D remains frozen prospective research evidence under its own governance.

It is excluded from:

- Phase 3C target metrics;
- calibration metrics;
- drift windows;
- automatic actions.

Phase 3C creates no Model 1D promotion authority.
