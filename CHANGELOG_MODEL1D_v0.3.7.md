# Model 1D v0.3.7 changelog

- Added read-only consumption of committed v0.3.6 fixed-horizon evidence.
- Added realised-family ranks and top-one, top-two, and top-three coverage.
- Added rank-two/rank-three probability-gap and entropy diagnostics.
- Added rank-three near-miss, rank-three miss, and deep-miss taxonomy.
- Added transition, confidence, adjacency, and dimension attribution.
- Added paired source-versus-rolling-frequency Brier and log-loss differences.
- Added fold win rates and circular block-bootstrap intervals.
- Preserved the April 2026 prospective shadow.
- Prohibited candidate or production promotion from the consumed sample.
## Schema and fold-reconstruction correction

- Prioritised `predicted_probabilities_json` over heuristic wide-column detection.
- Prioritised `actual_probabilities_json` for the soft realised target.
- Explicitly excluded `predicted_top_probability` from family-name inference.
- Reconstructed the seven overlapping v0.3.6 folds from `benchmark_fold_metrics.csv`.
- Added mandatory reconciliation against the four committed v0.3.6 source and rolling-frequency metrics.

## Final reconciliation correction

- Matched the v0.3.6 soft-log-loss floor of `1e-12`.
- Added source and rolling-frequency log-loss reconciliation gates.
- Documented that monthly dimension attribution is unavailable from the frozen
  v0.3.6 evidence.
- Replaced silent `insufficient_dimension_fields` output with the explicit
  `unavailable_from_frozen_v036_evidence` classification.
