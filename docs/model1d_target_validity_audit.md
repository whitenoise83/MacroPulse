# Model 1D v0.3.4 Target-Validity Audit

## Purpose

Earlier Model 1D research established that temporal smoothing, simple causal
bias correction, and hierarchical classification did not solve the failure to
beat persistence. v0.3.4 therefore audits the target rather than tuning another
classifier.

## Target construction

The forecast side is reconstructed from approved production-lineage vintage
backtests and is checked for information-cutoff violations. The realised side
uses the `actual` values stored in the approved backtest results. Those actuals
are ex-post evaluation outcomes; the current schema does not attach an explicit
revision-vintage timestamp to each realised value. The audit reports this
separately from forecast no-look-ahead compliance.

## Label stability

For each realised monthly score vector, the audit:

- recomputes the eight-state label;
- applies all 27 perturbation combinations at ±0.05, ±0.10, and ±0.25;
- measures base-label agreement, distinct labels, and full robustness;
- repeats the analysis at the five-family level;
- numerically searches for the nearest L-infinity label boundary;
- compares realised labels across sensitive, baseline, and conservative
  threshold definitions.

## Benchmarks

The same rolling-origin plan used by v0.3.1 is retained. Six pre-specified
benchmarks are reported:

- source direct classifier;
- previous realised regime persistence;
- expanding training-mode regime;
- rolling 12-month mode;
- first-order Markov transition prediction;
- a simple sign-rule mapping of the three forecast dimensions.

The consumed audit is evaluated only after the rolling summary is produced and
has no selection weight.

## Economic separation

For 1-, 3-, and 6-month horizons, the audit calculates eta-squared for future
levels and forward changes in growth, inflation, and labour. Results are shown
for both the eight-state and five-family targets. The incremental eight-state
value is the difference in mean eta-squared relative to the family target.

## Interpretation

The audit is intentionally difficult to pass. A target may fail even when its
forecast lineage is causal if its realised label is revision-ambiguous,
threshold-fragile, sparsely occupied, dominated by naive benchmarks, or lacks
incremental forward economic separation.
