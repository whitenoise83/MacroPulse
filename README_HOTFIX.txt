MacroPulse v0.6.1.post1 - Validation CLI reporting hotfix

This patch changes only scripts/run_validation.py.
It does not change model forecasts, model identity, configuration, database schema,
backtest results, or governance thresholds.

Fix:
- Reads passed/failed/warning counts from result['summary'].
- Prints failed and warning checks before the complete checks table.
- Avoids KeyError: 'passed'.
