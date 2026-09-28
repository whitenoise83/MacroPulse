# Model 3D — State-Space Potential Output Contract

## Purpose

Model 3D introduces the univariate unobserved-components state-space core for
Model 3. It estimates latent potential output, latent trend potential growth,
and a stationary cyclical output gap from real GDP.

Model 3D is an estimation workstream. It does **not** select a production
winner and it does not integrate Model 1 or Model 2.

## Governed input

The governed economic input is quarterly real GDP (`GDPC1`) expressed in
natural logs. The estimator is intentionally univariate. It must not require
the joint-complete GDP / unemployment / Core PCE panel merely to estimate the
GDP state-space model. This avoids truncating the univariate information set
because another series is unavailable.

A valid input series must:

- use a quarterly `PeriodIndex`;
- contain consecutive quarters;
- contain at least 40 observations;
- contain finite values.

When levels are supplied to a caller upstream, they must be strictly positive
before the natural-log transformation.

## State-space system

Let `y_t` denote log real GDP, `y*_t` latent log potential output, `g*_t`
latent quarterly trend growth, and `c_t` the cyclical output gap in log points.

Observation equation:

`y_t = y*_t + c_t`

Potential-output transition:

`y*_t = y*_{t-1} + g*_{t-1}`

Trend-growth transition:

`g*_t = g*_{t-1} + eta^g_t`

Gap transition:

`c_t = phi_1 c_{t-1} + phi_2 c_{t-2} + epsilon^c_t`

The state vector is:

`[y*_t, g*_t, c_t, c_{t-1}]'`

The trend-growth and cyclical innovations are Gaussian and mutually independent in 3D. Measurement error is fixed at zero because the decomposition itself supplies the observed GDP identity.

For identification, the direct potential-level innovation standard deviation is fixed at zero. An unrestricted five-parameter local-linear-trend plus AR(2) cycle specification exhibited likelihood pile-up of that variance at the numerical boundary during pre-freeze validation. Stochastic potential growth remains estimated through `eta^g_t`; potential output is therefore still time-varying and non-deterministic. The estimated trend-growth and gap innovation standard deviations must be strictly positive, and the AR(2) cyclical dynamics must be stationary.

## Estimation

The governed implementation uses the `statsmodels` state-space `MLEModel`
framework and Gaussian maximum likelihood. Diffuse initialization is used for
the nonstationary potential-output / trend-growth states.

The numerical environment requires NumPy, pandas, SciPy, and statsmodels
0.14 or later. Normalizing the project dependency manifest is deferred to
3I production hardening; 3D must not modify predecessor files for that purpose.

The governed optimizer is derivative-free Powell. Pre-freeze validation found unstable numerical gradients under L-BFGS/BFGS, while Powell converged on the identified smooth-trend specification. This optimizer choice is explicit and must not be silently substituted.

A fit is admissible only if optimization reports convergence and all transformed parameters are finite and satisfy the variance and AR(2) stationarity restrictions.

## Filtered, revised, and strict real-time estimates

Two estimate classes are deliberately exposed by the full-sample 3D fit:

- `filtered_full_sample_parameters`: the Kalman filtered state at each observation, conditional on parameters estimated from the complete supplied sample. State filtering is one-sided conditional on those parameters, but the estimate is not strict real-time because parameter estimation uses the full supplied sample.
- `smoothed_revised`: conditions on the full supplied sample and is revised by later observations.

Neither estimate class may masquerade as a strict real-time estimate.

Strict `filtered_real_time_endpoint` estimation is deferred to 3H pseudo-real-time evaluation. At each evaluation origin, model parameters must be estimated using only the information prefix available through that origin, and the terminal filtered state is retained. This prevents future observations from entering the origin estimate through parameter estimation.

Potential output in levels is `exp(y*_t)`.

The output gap is reported as:

`100 * (y_t - y*_t)`

Annualized potential growth is reported as:

`400 * g*_t`

The log-point gap is therefore expressed in the same first-order percentage
convention already used by Model 3C.

## Workstream boundary

3D does not use:

- unemployment;
- inflation;
- Phillips-curve restrictions;
- Okun-law restrictions;
- Model 1 current-state estimates;
- Model 2 forecasts or scenarios;
- automatic model selection;
- production database writes.

Multivariate slack belongs to 3E. Model 1 integration belongs to 3F. Model 2
forward-gap propagation belongs to 3G. Pseudo-real-time evaluation and model
selection belong to 3H.

Passing the 3D contract authorizes only 3E — Multivariate Macroeconomic Slack.
