# Model 3I Production Runbook

## Governed release

The planned first Model 3 production release is
`model3-potential-output-v1.0.0`. The selected specification is **3D — State-
Space Potential Output**, frozen by Model 3H. Model 3I does not retune the
econometric model.

## Current estimate

Production current-state estimation must call
`macropulse.slack.production.production_current_estimate` with an exact-vintage
Model 3 snapshot and an explicit release identity. The terminal filtered state
from an origin-truncated fit is exported as `production_current_endpoint`.

`smoothed_revised` is permitted only for revised historical analysis. The
full-sample filtered path must not be described as a real-time historical path.

## Required provenance

Every production current estimate carries the release identity, selected
candidate, as-of date, information-set ID, source snapshot hash, sample first
and last quarters, observation count, estimate class, and estimator diagnostics.

## Fail-closed behavior

Production must fail rather than emit an estimate when the 3D estimator fails
convergence/stationarity/near-unit-root/trend-innovation guards or when outputs
are non-finite. Model 2 GDP predictive draws are extracted by the governed
`real_gdp_growth` variable name, not by a hard-coded cube column. Dense
predictive-path horizons 1..8 are distinct from governed report horizons
1/2/4/8.

## Release evidence

Before tagging, require:
1. Model 3I contract and production tests.
2. Corrected no-lookahead archive audit.
3. Selected-3D fixed-quarter revision robustness record.
4. Model 3H empirical evidence SHA-256 manifest.
5. Real-data deterministic production smoke test.
6. Full Model 3 regression tests.
7. Frozen predecessor/Model 2 source integrity.
8. Successful branch CI under the Model 3 Potential Output Guard.

Only after branch CI passes should the final release record be frozen and the
immutable release tag created. No database write authority is granted by Model
3I.
