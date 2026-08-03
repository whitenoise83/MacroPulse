# MacroPulse Model 1D v0.3.2

## Regime-target and temporal-decision diagnostics

Model 1D v0.3.2 diagnoses why the v0.3.1 research stability leader did not
beat the strongest naive persistence baseline.

It deliberately does **not** reopen the normalization, weighting, threshold, or
uncertainty tournament. The source specification is fixed to the latest
successful v0.3.1 stability leader and remains a failed-promotion research
input.

## Diagnostic layers

1. Continuous growth, inflation, and labour score accuracy
2. Dimension-sign accuracy
3. Exact eight-regime accuracy
4. Broader regime-family accuracy
5. Stable-month versus transition-month accuracy
6. Transition precision, recall, F1, lead/lag, and false transitions
7. Per-regime precision and recall
8. Full eight-by-eight confusion matrix
9. Candidate-versus-persistence disagreement analysis
10. Regime occupancy and collapse diagnostics
11. Probability Brier score, log loss, and effective-regime diagnostics

## Temporal policies

Four fixed causal policies are evaluated across the same seven expanding-window
folds used by v0.3.1:

- `raw_monthly`
- `hysteresis_thresholds`
- `one_month_confirmation`
- `persistence_prior`

The 2024-08 to 2026-03 period is a consumed audit and has zero selection weight.

## Outputs

The command writes a Markdown report, metadata JSON, and CSV tables under:

`reports/macro_state_temporal/`

This version is research diagnostics only. It cannot approve a candidate or
production model.
