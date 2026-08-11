# MacroPulse Model 2 Plan — Bayesian VAR Forecasting & Scenarios

Model 2 is Roadmap Phase II — Forecasting & Scenarios, beginning from immutable
`phase3-evaluation-v1.0.1` at `edfc37b8f5f016710fb96402d205dcd35f2e09ca` on branch `model2-bvar-development`.

## Workstreams
2A specification/governance; 2B data/vintages; 2C baseline BVAR; 2D density
forecasts; 2E IRF/FEVD; 2F scenarios; 2G pseudo-real-time validation; 2H release.

## Initial system
GDPC1 real GDP growth; PCEPILFE core PCE inflation; UNRATE unemployment;
FEDFUNDS policy rate. Quarterly horizons: 1, 2, 4, 8.

## Initial BVAR family
Conjugate NIW with Minnesota-style shrinkage. Candidate lags 2/4 and overall
shrinkage 0.1/0.2/0.4. Candidate selection uses predeclared pseudo-real-time
development evidence and then freezes.

## Governance
Model 2 cannot mutate Models 1A–1C, tune from Model 1D prospective outcomes,
backfill Model 1D, move/recreate frozen tags, use future information, silently
substitute revised data for real-time vintages, use generative AI in the
governed core, or automatically switch/promote specifications.

The sole pre-existing-file amendment allowed in 2A is
`tests/test_phase3_bootstrap_contract.py`, only to make the frozen Phase III
release guard forward-compatible with later roadmap branches that descend from
the immutable `phase3-evaluation-v1.0.1` commit. Phase III evaluation/model semantics and the
release tag remain unchanged.
