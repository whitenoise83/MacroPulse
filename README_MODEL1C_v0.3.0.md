# MacroPulse Model 1C v0.3.0

## Prior-only labour interval calibration

This release adds a separate uncertainty-calibration layer to the completed
Model 1C vintage backtest. Point forecasts and realised outcomes are unchanged.

### Main changes

- Exponentially weighted empirical 80% intervals using strictly earlier target-month errors.
- 24-error warm-up and 48-month rolling calibration window.
- Interval coverage, half-width, and interval-score reporting.
- DuckDB calibration run and calibrated-result tables.
- Validation gates for strict prior-only cutoffs and calibration history.
- Explicit treatment of `UNRATE` October 2025 as structurally unavailable.
- Repair command for the existing v0.2.0 backtest metadata; no ALFRED rerun required.

### Commands

```cmd
python scripts\initialise_database.py
python scripts\repair_labour_structural_missing.py --backtest-id <BACKTEST_ID>
python scripts\calibrate_labour_intervals.py --backtest-id <BACKTEST_ID>
python scripts\run_labour_validation.py --backtest-id <BACKTEST_ID>
```

Model 1A and Model 1B remain frozen at v1.0.0 production.
