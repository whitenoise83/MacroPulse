# MacroPulse Model 1D v0.1.0 — Unified Macro State Foundation

This release starts Model 1D as a transparent aggregation layer over the
production GDP, inflation, and labour engines.

## Included

- Production-source registry checks
- As-of source-run selection
- Eight governed input forecasts
- Growth, inflation, and labour scores bounded from -2 to +2
- Explicit macro-regime rules
- Interval-derived confidence
- Cross-source cutoff synchronization checks
- Risk flags
- Prior-state score changes
- DuckDB persistence
- Provenance and state hashes
- Streamlit page
- Unit and integration tests

## Not yet included

- Historical pseudo-real-time state reconstruction
- Statistical threshold estimation
- Probabilistic regime classification
- State-transition matrices
- Outcome validation
- Production approval

Those are planned for Model 1D v0.2 and later.
