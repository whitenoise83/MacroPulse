# Changelog

## Model 1D v0.3.8

- Added an append-only prospective source-versus-rolling-frequency experiment.
- Added deterministic monthly prediction, fixed-horizon outcome resolution, and
  read-only monitoring.
- Added duplicate, no-look-ahead, target-availability, and 12-month evidence
  gates.
- Persisted the first genuine August 2026 prospective prediction.
- Froze the operational implementation at tag
  `model1d-v0.3.8-prospective-shadow-operational`.
- Retained lifecycle `development` and promotion authority `none`.

## Model 1C v1.0.0

- Promoted the governed labour nowcast to owner-approved production.
- Froze the stable 15-decision target-stage policy.
- Froze strictly prior `exp_weighted_q80` production intervals.
- Retained adaptive selection as shadow-only.
- Added guarded, evidence-verifying production promotion and monitoring.

## Model 1C v0.1.0

- Added the US labour-market nowcast foundation.
- Added payroll, unemployment-rate, and wage-growth targets.
- Added five development models, current-data runs, DuckDB persistence, and revised-data backtesting.
- Added dedicated labour dashboard pages while preserving Model 1A and Model 1B production identities.

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

## Model 1C v0.4.0

- Added stable labour policy and prior-only adaptive shadow tournament.
- Added common-sample, switching, regime, and calibrated interval diagnostics.
