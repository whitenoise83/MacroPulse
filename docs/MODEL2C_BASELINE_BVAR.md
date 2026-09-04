# Model 2C — Baseline Bayesian VAR

Model 2C begins from closed Model 2B.2 commit `90f529f635eeaa554259287ffc8a79647c92f7ad`. It implements the
baseline conjugate Bayesian VAR engine only. It does **not** select or rank a
candidate, choose an evaluation start, create predictive intervals, or grant
production authority.

## Candidate grid

The frozen 2A candidate grid is preserved: lags 2/4 crossed with overall
shrinkage 0.1/0.2/0.4, for six candidates. Model 2C must be able to estimate
all admissible candidates but may not choose among them.

## Conjugate prior

The baseline uses a matrix-normal inverse-Wishart posterior with
Minnesota-style shrinkage. The prior mean on the first own lag is zero for the
already-transformed GDP-growth and core-PCE-inflation variables, and one for
the level unemployment and policy-rate variables. Other lag means are zero.

Conditional coefficient-prior variance decays with lag squared and is scaled
by the estimation-panel sample variance of the predictor. The intercept is
weakly shrunk with variance 1e6. The inverse-Wishart prior uses df `m+2` and a
diagonal scale based only on the contemporaneous estimation panel.

This is empirical-Bayes scaling using information inside the exact estimation
vintage only; it does not use future vintages.

## Estimation and forecast object

Model 2C calculates the analytical conjugate posterior and stores the posterior
mean coefficient matrix, coefficient covariance, inverse-Wishart scale/df,
expected residual covariance, and posterior-mean companion spectral radius.

The only forecast in 2C is the recursive **posterior-mean point forecast** at
1, 2, 4 and 8 quarters. Posterior predictive simulation, density forecasts and
50/80/95 intervals belong to 2D.

The point-forecast API requires the exact estimation-panel hash, preventing a
posterior fitted to one vintage from being silently combined with another
history.

## Stability

The posterior-mean companion spectral radius is descriptive in 2C. It does not
automatically exclude, rank or promote a candidate. Any later stability rule
must be separately governed.

## CI dependency-compatibility maintenance

The Model 2C CI run exposed a repository-wide compatibility failure under statsmodels 0.15: `AutoReg(..., old_names=False)` is no longer accepted because the deprecated `old_names` keyword was removed. Model 2C maintenance therefore removes only that keyword from the pre-existing AR(1) helper. This is a compatibility-only change: statsmodels 0.14 already defaulted `old_names` to false, so Model 1 forecast semantics are unchanged.

## Boundaries

Historical Model 1 outputs are not backfilled. Model 1D prospective outcomes
are excluded. No estimation/evaluation start is chosen. No candidate is
selected. No production authority is granted.
