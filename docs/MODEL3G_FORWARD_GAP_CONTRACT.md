# Model 3G — Model 2 Forward-Gap Integration

## Boundary

Model 3G is a read-only downstream consumer of frozen Model 2 and frozen Model 3.
Its exact predecessor is `effb612f0d637a217fd00b563a8efafb69156983`.

It does not refit or mutate Model 2, select between Model 3E-A and Model 3E-B,
write to DuckDB, or promote a production specification.

## Governed probabilistic input

Model 2's posterior-predictive draw cube is the governed probabilistic input.
The governed forecast horizons are 1, 2, 4 and 8 quarters. Model 3G must preserve
draw identity and joint path alignment; point forecasts or marginal intervals are
not substitutes for the draw cube.

The Model 2 real-GDP variable is a growth rate. Model 3G therefore compounds each
GDP-growth draw path from an explicitly supplied real-GDP level at the forecast
origin. It must never treat GDP-growth draws as GDP levels.

## Potential-output continuation

Historical and current potential output remain Model 3-owned. Model 2 cannot
redefine them. In 3G the baseline potential path is a deterministic continuation
from a supplied Model 3 origin potential log level and quarterly trend-growth
state. This deliberately does **not** claim a full future potential-output
distribution. Potential-process uncertainty is a later research extension and
must not be silently manufactured here.

For horizon h,

`log(Y*_{t+h}) = log(Y*_t) + h g*_t`

under the baseline deterministic continuation.

For each Model 2 predictive draw d,

`Gap[d,h] = 100 * (log(Y[d,t+h]) - log(Y*_{t+h}))`.

## Scenario boundary

Model 2F scenarios are deterministic hard-path constraints around an
unconditional baseline. They are not Bayesian conditional densities, do not
carry scenario probabilities, and are not causal effects. 3G therefore does not
turn those scenario paths into probabilistic forward-gap densities.

## Labels and evaluation

The output estimate class is
`forward_distribution_from_model2_gdp_uncertainty_with_deterministic_model3_potential_continuation`.

It must not be described as a full joint GDP/potential uncertainty distribution.
Strict pseudo-real-time evaluation and any Model 3 candidate selection remain 3H.

Passing 3G authorizes only Model 3H.

## Dense Model 2 predictive-path adapter

3G obtains exact quarter-by-quarter GDP-growth paths by calling the existing frozen `simulate_posterior_predictive` function read-only with horizons 1 through 8. Model 2 source, posterior and production interfaces are not modified or refitted.

The dense call has its own draw hash because Model 2 hashing includes requested horizons, array shape and draw bytes. 3G records that dense hash separately and reports final gaps only at horizons 1, 2, 4 and 8.
