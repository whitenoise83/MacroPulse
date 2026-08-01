# MacroPulse Model 1C v0.5.0 — Candidate Validation

This incremental release formalises the stable 15-decision labour point policy and
`exp_weighted_q80` prior-only intervals as Model 1C candidates. The adaptive
selector remains a shadow challenger.

It adds `scripts/run_labour_candidate_validation.py`, which reuses the completed
vintage backtest and interval calibration. It makes no FRED/ALFRED requests.

This is not a production freeze. Models 1A and 1B remain unchanged at v1.0.0
production.
