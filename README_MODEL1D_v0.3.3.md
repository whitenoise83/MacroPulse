# MacroPulse Model 1D v0.3.3

Model 1D v0.3.3 adds causal dimension calibration and a hierarchical regime
decision diagnostic. It is a focused research release, not a new broad
hyperparameter tournament.

## Fixed source specification

The release uses the v0.3.1 rolling-origin research leader as its immutable
source specification:

- normalization: `expanding_robust_z`
- inflation weights: `policy`
- labour weights: `equal`
- thresholds: `sensitive`
- uncertainty: `independent_normal`

The source candidate failed promotion gates. v0.3.3 therefore cannot be
promoted merely because one calibration or hierarchy ranks first.

## Calibration candidates

1. `none`
2. `expanding_bias`
3. `expanding_affine_shrinkage`

Each fold estimates dimension-level parameters using only that fold's training
history. Growth, inflation, and labour are calibrated independently. Interval
bounds receive the same causal affine transformation as point scores.

The affine method shrinks its slope toward one and applies explicit slope and
intercept bounds to reduce small-sample instability.

## Decision architectures

1. `direct_eight_state`
2. `family_first`
3. `family_first_interval_abstain`

The family-first architecture first assigns one of five broad families:

- contraction
- adverse supply
- inflationary expansion
- benign expansion
- mixed

It then assigns an eight-regime subtype. The interval-abstention variant emits
`mixed_transition` whenever the dimension interval corners imply more than one
broad family.

## Evaluation

The same seven v0.3.1 rolling-origin folds are retained. The 2024-08 to 2026-03
period remains a consumed audit and has zero selection weight.

The diagnostics emphasize:

- macro-F1
- balanced accuracy
- family macro-F1
- family balanced accuracy
- baseline margin
- transition recall
- false-transition rate
- dimension RMSE
- regime-collapse rate
- block-bootstrap accuracy margin

No candidate is approved unless all governance gates pass.
