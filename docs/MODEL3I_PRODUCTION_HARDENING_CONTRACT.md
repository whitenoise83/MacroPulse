# Model 3I - Production Hardening & Release Contract

## Boundary
Model 3I begins from immutable Model 3H tag `model3-pseudo-real-time-v1.0.0`,
commit `a8ebf2d05a3b49d0c21f5ab1b03ca6eefca0b094`.

The governed selected candidate is **3D - State-Space Potential Output**.
3I may harden and expose that estimator. It may not retune the econometric model
or reopen the 3H selection.

## Production estimate semantics
The production current-state estimate is the terminal filtered estimate from a fit
using the governed information set through the production origin. It must be
relabelled `production_current_endpoint`.

The smoothed path is revised history and remains labelled `smoothed_revised`.
A full-sample filtered historical path must never be described as historical
real-time evidence.

## Fail-closed provenance
Every production result must identify the release/candidate, as-of date,
information-set identity, snapshot hash, sample boundaries, observation count,
estimate class, and estimator diagnostics.

## Dependency hardening
`requirements.txt` already bounds statsmodels as `>=0.14.6,<0.16`. The package
metadata in `pyproject.toml` must be normalized in 3I without weakening that bound.

## Model 3G release audits
Before final Model 3 release, 3I must verify:
1. frozen Model 2 `real_gdp_growth` is exactly annualized q/q log growth
   `400*diff(log(GDPC1))`;
2. the GDP variable in predictive draws is selected by governed variable name,
   not a caller hard-coded cube index;
3. dense-path draw identity/horizons and governed report horizons have distinct,
   explicit provenance.

These are release gates, not permission to retune Model 2.

## Promotion
Bootstrap does not promote Model 3 to production, write production database state,
move predecessor tags, or create the final release tag. Final release is planned as
`model3-potential-output-v1.0.0` only after all 3I gates pass.
