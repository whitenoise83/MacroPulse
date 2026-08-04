# Changelog — Model 1D v0.3.6

## Added

- Locked the five-family `fixed_horizon_90d` target as the primary research target.
- Added explicit fixed-horizon state-availability and missing-evidence diagnostics.
- Prohibited latest-revised substitution for missing fixed-horizon observations.
- Added availability-consistent probabilistic benchmarks:
  - hard persistence;
  - soft persistence;
  - Dirichlet-smoothed persistence;
  - first-order Markov probabilities;
  - rolling empirical family frequencies.
- Added soft Brier score, log loss, top-two coverage, expected calibration error, reliability bins, and Brier decomposition diagnostics.
- Added rolling-fold comparisons and a block-bootstrap margin against soft persistence.
- Added CLI, Streamlit controls, documentation, and tests.

## Unchanged

- v0.3.1 source specification;
- normalisation, weights, thresholds, and uncertainty method;
- consumed 2024-08 to 2026-03 audit treatment;
- production status of Models 1A, 1B, and 1C;
- Model 1D lifecycle status remains development.

## Realised audit result

Governance result: FAIL

The frozen Model 1D source passed all fixed-horizon probabilistic audit gates except source top-two coverage. Observed top-two coverage was 0.5714285714 against the required threshold of 0.65.

The source ranked first by mean soft Brier score, beat the pre-specified soft-persistence reference in all seven folds, and achieved a strictly positive bootstrap lower margin. Failure of the predeclared top-two coverage gate prevents promotion.

Status: fixed-horizon probabilistic research evidence only. Model 1D remains development-stage and is not candidate or production approved.
