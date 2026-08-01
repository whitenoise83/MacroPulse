# MacroPulse Model 1C — US Labour Market Nowcast Model Card

## Status

- Model ID: `US_LABOUR_NOWCAST_1C`
- Version: `1.0.0`
- Lifecycle: production
- Owner approval: `APPROVE MODEL 1C FREEZE`
- Approval date: `2026-08-01T16:12:00+01:00`

## Targets

- Nonfarm payroll change (`PAYEMS`), thousands of jobs
- Unemployment rate (`UNRATE`), percent
- Average hourly earnings growth (`CES0500000003`), annualised monthly percent

## Approved point policy

| Target | Month open | After week 1 | After week 2 | Month end | Pre-report |
|---|---|---|---|---|---|
| Payrolls | 12-Month Mean | Equal-Weight Ensemble | Bridge Ridge | Bridge Ridge | Bridge Ridge |
| Unemployment | Equal-Weight Ensemble | Equal-Weight Ensemble | Equal-Weight Ensemble | Equal-Weight Ensemble | Equal-Weight Ensemble |
| Hourly earnings | Bridge Ridge | Bridge Ridge | Equal-Weight Ensemble | Equal-Weight Ensemble | Equal-Weight Ensemble |

The adaptive selector remains shadow-only.

## Uncertainty

- Method: `exp_weighted_q80`
- Nominal coverage: 80%
- Minimum prior errors: 24
- Rolling window: 48 months
- Decay: 0.94
- Historical aggregate coverage: 80.9%
- Target-stage range: 77.7%–84.2%

## Evidence

- Vintage backtest: `834e0655-ba81-4b96-b42c-e1cdda73b847`
- Calibration: `3576b19a-27b0-4ee4-bf59-910d9c821c1b`
- Candidate validation: `0540c6ee-2d96-493a-adfe-a76c5c91cf31`
- Operational validation: `f535fdc2-c75c-4da8-a0f8-e3d1b80416f3`
- Freeze assessment: `7eb22dae-54c8-423e-ad1e-9977db08d388`
- Governed live run: `56adddf6-2438-43cf-97b0-24e4801ac9a4`

## Limitations

Pandemic observations dominate full-sample payroll and unemployment RMSE.
Payroll estimates are revised. Annualised one-month wage growth can be
volatile. Production monitoring and versioned change control remain mandatory.
