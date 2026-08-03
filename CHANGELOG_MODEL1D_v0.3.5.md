# Changelog — Model 1D v0.3.5

## Added

- Initial-release, fixed 90-day, and latest-revised target reconstruction from
  locally stored source backtests, historical snapshots, and latest observations.
- Explicit actual release date, evaluation date, as-of date, snapshot-gap, and
  revision-from-initial evidence.
- Five-family soft target as the primary research target.
- Secondary eight-state subtype probabilities.
- Deterministic threshold-ensemble and score-perturbation uncertainty.
- Primary-family confidence, probability margin, ambiguity flag, and alternative
  plausible families.
- Soft-label Brier score, cross-entropy loss, top-two coverage, and
  confidence-weighted accuracy.
- Rolling source-versus-persistence comparison and block-bootstrap margin.
- Cross-vintage family/regime agreement and dimension revision diagnostics.
- Prospective-shadow isolation beginning 2026-04-30.
- Streamlit research UI and standalone audit CLI.

## Changed

- Model identity advanced from v0.3.4 to v0.3.5.
- The five-family state is now the primary v0.3.5 research target; the
  eight-state taxonomy is secondary.
- Historical identity regression tests now expect v0.3.5.

## Unchanged

- The v0.3.1 source specification remains frozen.
- The 2024-08 to 2026-03 audit remains consumed and report-only.
- No candidate or production approval is granted.
- No new DuckDB tables are added.
