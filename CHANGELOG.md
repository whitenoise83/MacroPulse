# Changelog

## Model 1B v1.0.0

- Promoted the governed US inflation nowcast to production after owner approval.
- Frozen the stable target-stage policy and `exp_weighted_q80` intervals.
- Retained adaptive selection as shadow-only.
- Added guarded production promotion, model card, runbook, and revalidation triggers.

## Model 1B v0.2.0

- Added ALFRED historical information-set caching for inflation backtests.
- Added four monthly release stages.
- Added target-period historical dataset construction.
- Added initial-release target outcome reconstruction.
- Added separate vintage backtest and validation tables.
- Added Model 1B vintage validation report.
- Updated Inflation Backtesting dashboard with vintage and revised-data tabs.
- Preserved Model 1A v1.0.0 production identity.

## Model 1B v0.1.0

- Added four inflation targets and baseline models.
- Added current-data nowcast, revised-data chronological backtest, and dashboard pages.
