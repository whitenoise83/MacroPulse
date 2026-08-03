# Model 1D v0.3.3: Causal Calibration and Hierarchical Regime Diagnostics

## Research question

The v0.3.2 diagnostics showed that inflation retained useful signal, while
growth was upward-biased and labour was downward-biased. The direct eight-state
mapping also lost information relative to broad regime families. v0.3.3 asks:

1. Does causal dimension calibration materially reduce those biases?
2. Does family-first classification improve balanced regime performance?
3. Can interval-aware abstention reduce false precision without collapsing the
   model into `mixed_transition`?
4. Does any controlled variant beat the strongest naive baseline across rolling
   folds with a positive block-bootstrap lower margin?

## Causality

Calibration parameters are estimated only from each fold's training sample.
The consumed audit is never used for selection. For the descriptive selection
path, each month is calibrated only with observations dated before that month.

## Candidate set

The candidate set is deliberately limited to nine combinations:

- three calibration methods;
- three decision architectures.

The earlier normalization, weighting, threshold, and uncertainty search is not
reopened.

## Hierarchy

The first layer assigns a broad family. The second assigns a subtype. The
interval-abstention architecture checks all eight corners of the three
dimension intervals. If those corners disagree on the broad family, the month
is labelled `mixed_transition`.

## Governance

A research leader remains unapproved unless it:

- beats the strongest naive baseline in most folds;
- achieves minimum macro-F1 and balanced accuracy;
- achieves minimum family macro-F1;
- retains transition recall;
- controls false transitions;
- avoids regime collapse;
- has a strictly positive block-bootstrap lower margin.
