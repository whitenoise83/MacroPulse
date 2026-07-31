# Changelog — Model 1B v0.6.0

## Added

- Governed live candidate run registry.
- Four target-specific governed headline records per run.
- All-component live forecast storage with governance roles.
- Persisted live information sets.
- Automatic target-period, release-date, and forecast-stage inference.
- Stable candidate policy control and separately stored adaptive shadow output.
- Exponentially weighted prior-only 80% live intervals.
- Model-state hash and canonical governance signature.
- Inflation news decomposition and observation-level release-change audit.
- Operational live validation and report generation.
- Inflation News Streamlit page.

## Changed

- Model 1B version advanced from `0.5.0` to `0.6.0`.
- `run_inflation_nowcast.py` now runs the governed candidate path.
- The development interval configuration now identifies `exp_weighted_q80`.
- The Inflation Nowcast page now displays the stable headline rather than a
  global preferred baseline model.

## Preserved

- Model 1A remains `US_GDP_NOWCAST_1A v1.0.0` production.
- Model 1B candidate validation evidence and vintage backtest results are reused.
- No ALFRED vintage backtest rerun is required.
- Existing inflation baseline forecasts remain available in their historical tables.
