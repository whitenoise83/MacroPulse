# MacroPulse Model 1C Vintage Validation

- Validation ID: `b2d86c3b-53ed-42a1-988c-ec274bc75bdc`
- Backtest ID: `834e0655-ba81-4b96-b42c-e1cdda73b847`
- Status: **CONDITIONAL**

## Checks

| Gate | Check | Status | Observed | Threshold |
|---|---|---:|---:|---:|
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
| Uncertainty calibration | Development 80% intervals are not grossly miscalibrated | warning | 7 groups outside range | each group between 50% and 95% |

## Interpretation

This development-stage validation confirms the release timing, vintage information sets, model completeness, and robust reporting architecture. It does not select a production champion or approve the raw residual-based intervals.