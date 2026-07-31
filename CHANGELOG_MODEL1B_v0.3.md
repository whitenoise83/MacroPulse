# MacroPulse Model 1B v0.3.0

## Added

- Prior-only rolling empirical interval calibration.
- Separate DuckDB calibration run and calibrated-result tables.
- `scripts/calibrate_inflation_intervals.py`.
- Validation gates for strict prior-only cutoff, minimum calibration history,
  calibrated evaluation depth, and post-calibration coverage.
- Dashboard support for calibrated coverage and warm-up classification.

## Changed

- Model 1B development version is now `0.3.0`.
- Package version is now `1.3.0.dev0`.
- Insufficient training history is classified as `warmup`, not a backtest issue,
  on future vintage runs.

## Unchanged

- All point forecasts.
- All stored vintage actuals and forecast errors.
- Model 1A v1.0.0 production specification and governance records.
