# Model 3E — Multivariate Macroeconomic Slack Contract

Model 3E extends exact predecessor `4a33072b8c2d767fb4eecdf6efc1aba879373ff2`.
It preserves the 3D GDP state system and sigma_potential=0 identification.

3E-A adds:
`pi_t = alpha_pi + rho_pi*pi_(t-1) + kappa*c_(t-1) + epsilon_pi_t`.

3E-B additionally adds:
`u_t = alpha_u + tau_u*T_t - lambda*c_t + epsilon_u_t`.

The unemployment trend is deterministic in 3E; a stochastic latent NAIRU is
not authorized. Expected Phillips/Okun signs are diagnostics, not hard
optimization constraints.

Full-sample fits are labelled `filtered_full_sample_parameters` and
`smoothed_revised`; neither is strict real-time. Strict recursive endpoint
estimation and production selection are deferred to 3H. Model 1 integration is
deferred to 3F and Model 2 forward-gap integration to 3G.

3E does not rank candidates, write production outputs, automatically promote
specifications, mutate predecessors, or use downstream Model 4 performance to
retune Model 3. Passing 3E authorizes only 3F.


## Corrected Model 3D predecessor and candidate diagnostics

Exact predecessor: `4a33072b8c2d767fb4eecdf6efc1aba879373ff2`. The corrected Model 3D initialization is inherited by 3E. The AR(2) minimum-root guard band is 1.02 and is a candidate diagnostic, not a production-selection rule. Phillips kappa and Okun lambda remain unrestricted; expected signs are recorded as evidence only. Production selection remains deferred to Model 3H.
