# MacroPulse Model 1B Vintage Validation

- Validation ID: `11ca9805-a847-4336-9b0e-ea2ffe0be9cb`
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
| Uncertainty calibration | Development 80% interval coverage is not grossly miscalibrated | warning | 39 groups outside range | each group between 60% and 95% |

## Interpretation

This is a development-stage vintage validation. Passing these checks confirms the information-set and release-timing architecture, not final production approval.