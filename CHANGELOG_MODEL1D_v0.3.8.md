# Changelog — Model 1D v0.3.8

## Prospective experiment

- Froze the exact Model 1D v0.3.6 source candidate.
- Added the causal `rolling_frequency` comparator.
- Froze the five-family probability contract and fixed-horizon 90-day target.
- Prohibited tuning, switching, blending, source replacement, and promotion.
- Required at least 12 complete prospective target months before formal comparison.

## Persistence

- Added append-only shadow run, prediction, dimension, and outcome tables.
- Added service-level and database-level duplicate protection.
- Added one-run, two-prediction, three-dimension monthly write invariants.
- Added exactly-two-outcome resolution invariants.
- Prohibited update, delete, upsert, replacement, and premature resolution.

## Prediction engine

- Added prior-only expanding robust-z normalisation with governed fallback.
- Preserved policy inflation weights and equal labour weights.
- Added deterministic independent-normal probability construction.
- Added causal rolling-frequency probabilities.
- Added rankings, entropy, probability hashes, source lineage, and no-look-ahead checks.
- Persisted the first genuine August 2026 prospective prediction.

## Outcome resolution

- Added strict fixed-horizon target reconstruction from cached historical snapshots.
- Added component-level availability checks.
- Added actual soft-family probabilities and confidence.
- Added Brier score, log loss, and top-one/top-two/top-three evaluation.
- Added previous-family and transition classification.
- Ensured incomplete targets remain unresolved without latest-revised substitution.

## Operations and monitoring

- Added an idempotent monthly operations runner.
- Added read-only status reporting and a Streamlit monitoring page.
- Added integrity, pending, due, resolved, comparison-readiness, and transition reporting.
- Added Markdown, JSON, and CSV operational outputs.
- Added the 12-complete-month governance lock.
- Verified duplicate-month protection and zero-row premature resolution.
- Excluded local DuckDB backups and generated monitoring reports from Git.

## Operational freeze

- Operational implementation commit: `6e1ff2a`
- Operational tag: `model1d-v0.3.8-prospective-shadow-operational`
- Repository-hygiene commit: `252caaf`
- First shadow run: `73ea26fd-a731-4d87-a735-ae1107a9c06c`
- Current conclusion: `insufficient_prospective_evidence`
- Promotion authority: `none`
