# Changelog — Model 1D v0.2.1

## Added

- Production-validation lineage resolution for Models 1A, 1B, and 1C
- Approved vintage-backtest reconstruction
- Exact monthly/quarterly target alignment
- Production stable-policy model selection
- Approved prior-only interval preference with transparent fallback
- Leakage and maximum-observation-date audits
- Source validation IDs and interval provenance
- Coverage ratio and longest contiguous-run metrics
- Gap-safe regime durations and transitions
- Vintage-history regression and integration tests

## Changed

- Historical CLI now defaults to `production_vintage_backtests`.
- Stored live-run reconstruction remains available with
  `--source-mode live_runs`.
