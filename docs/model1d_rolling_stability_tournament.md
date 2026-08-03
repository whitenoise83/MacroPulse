# Model 1D Rolling-Origin Stability Tournament

## Purpose

A single validation window can reward a specification that happens to fit one
macro episode. Model 1D v0.3.1 asks a stricter question: does a specification
remain competitive as the training information set expands and the evaluation
window moves through time?

## Selection and audit separation

The first 54 complete states form the selection sample. Seven expanding-window
folds are constructed within this sample. The last 19 complete states are the
previously observed v0.3 audit period. Audit results are disclosed after
selection but have zero weight in the stability score.

## Fold structure

Each fold contains all information from the start of the reconstructed history
through its training cutoff. The next six complete states form the evaluation
window. The training cutoff advances by three complete states between folds.

This creates overlapping evaluation windows. Fold-rank stability and moving
block bootstrap intervals are both reported so that overlap is not mistaken
for independent evidence.

## Baselines

Each core specification defines its own realised regime history through its
normalization, weights, and thresholds. Baselines are therefore calculated
within each candidate and fold:

1. the most frequent training-period realised regime;
2. the previous contiguous month's realised regime.

The stronger fold-level baseline is used for the dominance gate and bootstrap
accuracy-margin diagnostic.

## Selection rule

Final ranking combines core and uncertainty fold scores using the unchanged
70/30 v0.3 weights. Aggregate stability ranking rewards high mean and median
scores, stable ranks, repeated leading-third placement, baseline dominance,
and uncertainty-method consistency. Average regret is penalized.

## Candidate gates

The stability leader is blocked from promotion when any configured gate fails.
The audit rank is never a selection gate because using it would tune on the
consumed audit sample; it is nevertheless shown prominently as external
robustness evidence.

## Limitations

- The reconstructed history is short and contains one governed missing month.
- Rolling evaluation windows overlap.
- Realised regimes are specification-dependent rather than externally labelled.
- The uncertainty tournament remains a statistical diagnostic rather than a
  structural regime-probability model.
- Passing v0.3.1 does not replace later candidate validation and freeze review.
