# MacroPulse Model 1D v0.3.0

This release adds the governed normalization, weighting, threshold, and
uncertainty tournament for the Unified US Macro State Engine.

## Tournament structure

### Core stage

- 3 normalization candidates
- 3 inflation weighting candidates
- 3 labour weighting candidates
- 3 threshold candidates
- 81 core specifications

### Uncertainty stage

The top 12 core specifications are paired with 3 joint uncertainty methods:

- independent normal
- fixed Gaussian copula
- expanding residual copula

This creates 36 final candidates.

## Chronological safeguards

- no random train/test split;
- 36-state training window;
- 18-state validation window;
- remaining states reserved as holdout;
- expanding normalization uses only prior realised targets;
- holdout performance does not select the winner;
- missing months remain missing;
- churn metrics use only contiguous months.

## Evaluation

Core specifications are ranked using dimension accuracy, regime accuracy,
regime-family accuracy, sign accuracy, churn coherence, and regime-distribution
coherence, and a threshold-collapse penalty.

Uncertainty methods are ranked using multiclass Brier score, log loss, 80%
probability-set coverage, effective regime count, and top-regime accuracy.

## Outputs

- DuckDB tournament run registry
- complete core and final candidate registry
- validation and holdout metrics
- monthly probabilistic audit for all final candidates
- provisional winner
- naive mode and persistence baselines
- Markdown tournament report
- Streamlit leaderboard and winner audit

The selected specification remains provisional and is not production approved.
