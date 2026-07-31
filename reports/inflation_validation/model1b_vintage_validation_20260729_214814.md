# MacroPulse Model 1B Vintage Validation

- Validation ID: `229d1387-a894-4bba-9be1-8cfc05bad9a3`
- Backtest ID: `fdd2f573-a425-4abc-8056-f9843955bac2`
- Status: **CONDITIONAL**

## Checks

| Gate | Check | Status | Observed | Threshold |
|---|---|---:|---:|---:|
| Data integrity | One forecast per target, stage, month, and model | pass | 0 | 0 duplicates |
| Econometric validity | Forecast cutoff occurs before the initial target release | pass | 0 | 0 violations |
| Econometric validity | No observation is dated after the information cutoff | pass | 0 | 0 future-dated information sets |
| Econometric validity | Target-month index is absent before its initial release | pass | 0 | 0 leaked forecasts |
| Reproducibility | Every forecast has a valid information-set hash | pass | 0 | 0 invalid hashes |
| Data integrity | Every evaluated information set contains all declared models | pass | 0 | 0 incomplete groups |
| Econometric validity | Minimum evaluated months for every target and stage | pass | 73 | >= 36 |
| Data integrity | All declared release stages are represented for every target | pass | 0 | 0 incomplete targets |
| Econometric validity | Every forecast satisfies the configured training minimum | pass | 120 | >= 120 months |
| Uncertainty calibration | Prior-only interval calibration is available | pass | 3272 calibrated rows | > 0 calibrated rows |
| Econometric validity | Interval calibration uses strictly prior target-month errors | pass | 0 | 0 look-ahead violations |
| Uncertainty calibration | Every calibrated interval satisfies the prior-error minimum | pass | 24 | >= 24 prior errors |
| Uncertainty calibration | Minimum evaluated calibrated intervals for every target, stage, and model | pass | 49 | >= 36 |
| Uncertainty calibration | Prior-only 80% interval coverage is not grossly miscalibrated | warning | 17 groups outside range | each group between 60% and 95% |

## Interpretation

This is a development-stage vintage validation. Passing these checks confirms the information-set and release-timing architecture, not final production approval.