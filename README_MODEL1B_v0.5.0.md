# MacroPulse Model 1B v0.5.0 — Candidate Validation

This incremental release formalises the stable target-stage point policy and
`exp_weighted_q80` prior-only intervals as Model 1B candidates. The adaptive
selector remains a shadow challenger.

It adds `scripts/run_inflation_candidate_validation.py`, which reuses the
completed vintage backtest and makes no FRED/ALFRED requests.

This is not a production freeze. Model 1A v1.0.0 is unchanged.
