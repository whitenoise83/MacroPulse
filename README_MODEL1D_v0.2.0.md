# MacroPulse Model 1D v0.2.0

This release adds historical pseudo-real-time reconstruction to the transparent
Model 1D macro-state engine.

## Added

- Monthly reconstruction dates
- Vintage-safe source selection
- Cross-version historical source support
- No-look-ahead audit
- Historical growth, inflation, and labour scores
- Uncertainty-aware possible-regime sets
- Regime duration analysis
- Transition matrix
- DuckDB persistence
- CLI and Streamlit history views
- Unit and integration tests

## Important limitation

The engine can reconstruct only months for which complete source-run histories
exist in the MacroPulse database. It will skip months without a complete GDP,
inflation, and labour bundle.
