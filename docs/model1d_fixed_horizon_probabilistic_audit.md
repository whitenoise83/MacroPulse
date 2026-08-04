# Model 1D v0.3.6 — Fixed-Horizon Target Lock and Probabilistic Benchmark Audit

## Purpose

Model 1D v0.3.6 does not change the source forecast model. It locks the five-family fixed-90-day realised target as the primary research target and evaluates the frozen source probabilities against causal probabilistic benchmarks.

The eight-state regime remains a report-only subtype. Latest-revised observations cannot replace missing fixed-horizon evidence.

## Locked target

- Primary target mode: `fixed_horizon_90d`
- Primary target level: five macro families
- Secondary target level: eight-state subtype, report only
- Governance reference: `soft_persistence`
- Latest-revised substitution: prohibited
- Prospective shadow start: 2026-04-30

## Availability-consistent benchmark construction

For every forecast month, a benchmark may use only historical target states whose fixed-horizon evaluation date has already passed. The audit records the latest target month and target-availability date used by every benchmark prediction.

The benchmark set is fixed before evaluation:

1. `source` — frozen Model 1D family probabilities;
2. `hard_persistence` — one-hot probability on the latest available family;
3. `soft_persistence` — latest available soft family distribution;
4. `dirichlet_persistence` — soft persistence with symmetric smoothing;
5. `markov_first_order` — smoothed transition probabilities conditional on the latest available family;
6. `rolling_frequency` — empirical family frequencies over the latest twelve available target states.

## Missing evidence

The audit separately records every missing fixed-horizon target observation, its target month, requested evaluation date, available snapshot date, and availability status. Incomplete states are not silently completed with latest-revised data.

## Metrics

The rolling-origin evaluation reports:

- family accuracy;
- family balanced accuracy;
- family macro-F1;
- confidence-weighted accuracy;
- soft Brier score;
- soft log loss;
- top-two coverage;
- mean probability assigned to the realised family;
- expected calibration error;
- hard-label multiclass Brier decomposition diagnostics;
- reliability by probability bin;
- fold win rate against soft persistence;
- block-bootstrap confidence interval for the confidence-weighted monthly margin.

## Governance

The research architecture cannot pass unless:

- fixed-horizon state completeness is at least 95%;
- all incomplete states are explicitly documented;
- no latest-revised substitution is allowed;
- all benchmarks pass availability no-look-ahead checks;
- the source beats soft persistence in at least 60% of folds;
- the bootstrap lower margin is strictly positive;
- source macro-F1 is not lower than soft persistence;
- source soft Brier score improves on soft persistence;
- source expected calibration error is no greater than 0.20;
- source top-two coverage is at least 65%;
- the prospective shadow remains isolated.

A passing audit is research evidence only. It does not approve Model 1D for production.

## Realised audit result

Governance result: FAIL

The frozen Model 1D source passed all fixed-horizon probabilistic audit gates except source top-two coverage. Observed top-two coverage was 0.5714285714 against the required threshold of 0.65.

The source ranked first by mean soft Brier score, beat the pre-specified soft-persistence reference in all seven folds, and achieved a strictly positive bootstrap lower margin. Failure of the predeclared top-two coverage gate prevents promotion.

Status: fixed-horizon probabilistic research evidence only. Model 1D remains development-stage and is not candidate or production approved.
