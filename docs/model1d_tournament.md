# Model 1D v0.3 Tournament Design

Model 1D v0.3 compares transparent alternatives for four design choices:

1. target normalization;
2. within-dimension weights;
3. regime thresholds;
4. joint uncertainty.

The tournament uses the latest production-lineage pseudo-real-time history and
joins each historical forecast to the realised target stored in the approved
backtest. It does not use revised values from a different model lineage.

## Chronological design

The default 73-state sample is divided without random shuffling:

- first 36 complete states: training and expanding-normalization history;
- next 18 states: validation and model selection;
- remaining states: sealed holdout audit.

The missing October 2025 state remains missing. Transition and churn metrics
only use contiguous month pairs.

## Stage 1: core specification

The core grid contains 81 candidates:

- 3 normalization methods;
- 3 inflation weight sets;
- 3 labour weight sets;
- 3 threshold sets.

Each candidate is evaluated against realised dimension scores and realised
regimes. Selection metrics are:

- dimension RMSE;
- exact regime accuracy;
- regime-family accuracy;
- dimension sign accuracy;
- forecast-versus-realised churn gap;
- Jensen-Shannon divergence between forecast and realised regime frequencies;
- a regime-collapse penalty when threshold choices produce too little state diversity.

Metric ranks are combined using the governed weights in
`config/macro_state_governance.yml`.

## Normalization candidates

### Policy anchors

The v0.1 configured piecewise anchors.

### Target-centred

A fixed centre-and-scale transformation with explicit economic reference
points. It is fully deterministic and does not learn from the tournament
sample.

### Expanding robust z-score

The median and MAD are estimated only from realised target periods strictly
before the current target period. A fixed target-centred fallback is used until
minimum history is available. Future actuals cannot alter an earlier score.

## Stage 2: uncertainty

Only the top 12 core specifications enter the uncertainty stage. Each is paired
with:

- independent normal dimension errors;
- fixed Gaussian copula;
- expanding residual copula with shrinkage.

This creates 36 final candidates. Their validation metrics are:

- multiclass Brier score;
- log loss;
- realised-regime coverage of the 80% cumulative probability set;
- effective number of regimes;
- top-regime accuracy.

The final validation score combines 70% core score and 30% uncertainty score.
The winner is then audited, but not reselected, on the sealed holdout.

## Governance status

The output is a provisional research winner. It is not a candidate approval,
freeze decision, or production promotion. A later release must test rank
stability, subperiod performance, event sensitivity, and calibration before a
Model 1D candidate can be proposed.
