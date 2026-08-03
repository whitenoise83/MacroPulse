# Changelog — Model 1D v0.3.1

## Added

- Expanding-window rolling-origin tournament plan
- Seven chronological evaluation folds
- Separate consumed external audit sample
- Candidate-specific training-mode and persistence baselines
- Mean, median, dispersion, worst-rank, win-rate, regret, and leading-third
  stability diagnostics
- Naive-baseline dominance gates
- Uncertainty-method fold win rates
- Proper-score dominance against independent normal
- Moving-block bootstrap confidence intervals
- Macro-subperiod diagnostics
- Rolling stability database tables
- Rolling stability CLI, report, and Streamlit panel
- Unit, pipeline, and persistence tests

## Changed

- Model identity advanced from v0.3.0 to v0.3.1 development
- The v0.3.0 holdout is explicitly treated as a consumed audit and is excluded
  from ranking

## Preserved

- 81 core specifications
- 12 core finalists and 3 uncertainty methods
- Production-vintage Model 1D historical reconstruction
- October 2025 evidence gap
- No-look-ahead normalization and uncertainty estimation
- v0.3.0 research tournament records
