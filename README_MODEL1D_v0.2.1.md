# MacroPulse Model 1D v0.2.1

Model 1D v0.2.1 reconstructs historical monthly macro states from the
production-approved validation lineages of Models 1A, 1B, and 1C.

## Source lineage

- Model 1A: approved staged GDP backtest linked through `validation_runs`
- Model 1B: approved inflation vintage backtest linked through
  `inflation_validation_runs`
- Model 1C: approved labour vintage backtest linked through
  `labour_validation_runs`

The engine does not simply choose the newest backtest. It uses the backtest
actually approved by each production model's candidate/freeze process.

## Monthly alignment

For each month end:

- GDP uses the same-quarter production stage:
  - first month: `early_quarter`
  - second month: `after_month_1`
  - third month: `quarter_end`
- inflation uses the target month's `month_end` stage;
- labour uses the target month's `month_end` stage;
- all targets must match the state month or quarter exactly.

## Audits

- forecast date must not exceed state date;
- target-leakage flags must be false;
- maximum observation date must not exceed forecast date;
- all eight required inputs must be present;
- transitions are calculated only between contiguous months;
- regime durations break at missing-month gaps.

The expected common sample is governed by the approved source histories. Based
on the current database coverage it should begin around February 2020 and end
with the latest completed GDP target quarter available in the staged backtest.
