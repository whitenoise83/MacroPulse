# Model 1B v0.5.0

- Retained the stable 16-decision target-stage policy as the point candidate.
- Retained the prior-only adaptive selector as shadow-only after matched-sample verification.
- Selected `exp_weighted_q80` as the interval candidate.
- Added formal candidate validation for timing, leakage, reproducibility, relative accuracy, bias, challenger stability, and interval quality.
- Added a governed Markdown candidate-validation report and DuckDB validation record.
- Preserved Model 1A v1.0.0 and all existing vintage snapshots/backtests.
