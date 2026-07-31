# MacroPulse Model 1C Vintage Validation

- Validation ID: `94be6d19-51a2-4ba6-8956-a2d9d4e16df5`
- Backtest ID: `834e0655-ba81-4b96-b42c-e1cdda73b847`
- Status: **PASS**

## Checks

| Gate | Check | Status | Observed | Threshold |
|---|---|---:|---:|---:|
| Operational reliability | Vintage backtest contains no unresolved hard issues | pass | 0 | 0 unresolved hard issues |
| Data availability | Structurally unavailable target months are explicitly documented | pass | 1 | documented exclusions allowed |
| Data integrity | One forecast per target, stage, month, and model | pass | 0 | 0 duplicates |
| Econometric validity | Forecast cutoff occurs before the initial target release | pass | 0 | 0 violations |
| Econometric validity | No observation is dated after the information cutoff | pass | 0 | 0 future-dated information sets |
| Econometric validity | Target-month outcome is absent before its initial release | pass | 0 | 0 leaked forecasts |
| Reproducibility | Every forecast has a valid information-set hash | pass | 0 | 0 invalid hashes |
| Data integrity | Every evaluated information set contains all declared models | pass | 0 | 0 incomplete groups |
| Data integrity | All declared release stages are represented for every target | pass | 0 | 0 incomplete targets |
| Econometric validity | Minimum evaluated months for every target and stage | pass | 109 | >= 36 |
| Econometric validity | Every forecast satisfies the configured training minimum | pass | 120 | >= 120 months |
| Econometric validity | Every forecast has positive lead time to release | pass | 0 | 0 non-positive lead times |
| Performance reporting | Robust error and regime fields are complete | pass | 0 | 0 incomplete rows |
| Performance reporting | All declared economic regimes are represented for every target | pass | 0 | 0 incomplete targets |
| Uncertainty calibration | Prior-only interval calibration is available | pass | 6895 calibrated rows | > 0 calibrated rows |
| Econometric validity | Interval calibration uses strictly prior target-month errors | pass | 0 | 0 look-ahead violations |
| Uncertainty calibration | Every calibrated interval satisfies the prior-error minimum | pass | 24 | >= 24 prior errors |
| Uncertainty calibration | Minimum evaluated calibrated intervals for every target, stage, and model | pass | 85 | >= 36 |
| Uncertainty calibration | Prior-only 80% interval coverage is not grossly miscalibrated | pass | 0 groups outside range | each group between 60% and 95% |
| Uncertainty calibration | Calibrated interval scores are finite and reportable | pass | 0 | 0 invalid interval scores |

## Interpretation

This development-stage validation confirms release timing, vintage information sets, model completeness, documented structural exclusions, and prior-only interval calibration. It does not yet select or approve a production point-forecast policy.