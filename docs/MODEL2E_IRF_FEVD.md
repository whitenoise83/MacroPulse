# Model 2E — Recursive IRF and FEVD

Model 2E begins from the closed Model 2D probabilistic-forecast workstream at
`a40c5f3f5426982f5d23781ad26467c97be501c8`, validated by Model 2 Bayesian VAR Guard run `33891568448`.

It adds structural impulse-response functions (IRFs) and forecast-error variance
decompositions (FEVDs). It does not select or rank a Model 2 candidate.

## Identification

The frozen Model 2A recursive ordering is:

1. real GDP growth;
2. core PCE inflation;
3. unemployment rate;
4. federal funds rate.

Identification uses the lower Cholesky factor of the posterior expected
reduced-form residual covariance. A structural shock is normalized to one
standard deviation. The contemporaneous zero restrictions are therefore those
implied by this ordering.

The VAR dynamics use posterior-mean coefficients. Structural results are point
objects conditional on the posterior summary and the recursive identification.
They are not unconditional causal claims.

## IRF

Moving-average matrices are computed recursively from the posterior-mean VAR.
The horizon-zero impact matrix is computed internally. Governed reported
horizons are 1, 4, 8 and 12 quarters.

For horizon `h`, the orthogonalized response matrix is `Psi_h @ P`, where `P`
is the lower Cholesky impact matrix.

Posterior credible bands for IRFs are not introduced in this baseline 2E
contract.

## FEVD

For forecast horizon `H`, the contribution of structural shock `j` to response
`i` is the cumulative squared orthogonalized response from steps `0..H-1`,
divided by the total cumulative forecast-error variance for response `i`.

Shares must be finite, lie in `[0, 1]` up to numerical tolerance, and sum to one
for every response/horizon pair.

## Boundaries

All six Model 2C candidates remain separately admissible. There is no candidate
selection, ranking, automatic exclusion or promotion in 2E. Historical Model 1
outputs are not backfilled. Model 1D prospective outcomes remain excluded.
Scenario conditioning remains 2F; pseudo-real-time model comparison remains 2G.
Production authority remains none.
