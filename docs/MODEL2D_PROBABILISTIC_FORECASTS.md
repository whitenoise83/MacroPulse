# Model 2D — Probabilistic Forecasts and Uncertainty

Model 2D begins from the closed Model 2C baseline at `b321e3f59ac7165cf71b1b3155712312b58af1a7` with green Model 2 Bayesian VAR Guard run `33888716133`. It adds posterior-predictive simulation and uncertainty summaries only. It does not select or rank a Model 2 candidate.

## Posterior predictive simulation

Each simulated path draws one residual covariance matrix from the conjugate inverse-Wishart posterior, then draws one coefficient matrix from the matrix-normal conditional posterior. The path is propagated recursively and a new multivariate innovation is drawn at every future quarter. This includes both parameter uncertainty and future innovation uncertainty.

No posterior draw is rejected or truncated using a stability criterion. The system contains level variables with unit-root-style prior means, so imposing an unannounced stationarity filter would change the governed posterior.

## Reproducibility

The canonical default seed is `20260904` and the canonical default simulation count is `5000`. The seed, simulation count, exact estimation-panel hash, candidate ID and draw hash are recorded. The exact estimation panel used to fit the posterior must also be supplied for simulation.

## Forecast summaries

The governed horizons remain 1, 2, 4 and 8 quarters. Model 2D reports posterior predictive mean, median and standard deviation plus central 50%, 80% and 95% intervals for each variable and horizon.

These are probabilistic model outputs, not empirical calibration claims. Coverage, log predictive density, CRPS and interval-score evaluation belong to 2G.

## Boundaries

All six Model 2C candidates remain admissible and are simulated independently. There is no candidate selection, ranking, automatic exclusion or promotion in 2D. Scenario conditioning belongs to 2F. Historical Model 1 outputs are not backfilled, Model 1D prospective outcomes remain excluded, no evaluation start is chosen, and production authority remains none.
