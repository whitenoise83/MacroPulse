# Model 2F — Conditional Path Scenario Analysis

Model 2F begins from the closed Model 2E structural-analysis workstream at
`559c581f6155f16c275e4523d67a8479310bf337`, validated by Model 2 Bayesian VAR Guard run `35747825040`.

It adds deterministic conditional-path scenarios around the Model 2 baseline.
It does not select or rank a BVAR candidate and does not attach probabilities
to scenarios.

## Baseline

The baseline is the unconditional recursive posterior-mean path from the exact
estimation panel. The engine propagates all eight future quarterly states because
scenario constraints at an intermediate horizon must feed into subsequent model
states.

The standard reporting horizons remain 1, 2, 4 and 8 quarters.

## Hard path constraints

A scenario is a table of `(horizon, variable, value)` constraints. Horizons may
be 1 through 8 and variables must be one of the four governed Model 2 variables.

At each future quarter the BVAR first computes its posterior-mean prediction.
Any scenario constraint for that quarter then replaces the corresponding
predicted value. The resulting constrained state is fed into later recursive
forecasts.

Duplicate constraints for the same variable/horizon, unknown variables,
out-of-range horizons and non-finite values fail closed.

## Interpretation

This is a **mechanical deterministic scenario path**. It is not a Bayesian
conditional density, does not estimate the probability of the scenario, and
does not by itself identify a causal effect.

The reported deviation is simply:

`scenario path - unconditional baseline path`

Model 2E recursive structural identification is not silently invoked for these
hard-path scenarios. Structural-shock causal language therefore may not be
attached to 2F path deviations.

## Governance

All six Model 2C candidates remain separately admissible. No candidate
selection, ranking, automatic exclusion or promotion occurs in 2F. Historical
Model 1 outputs are not backfilled, Model 1D prospective outcomes remain
excluded, pseudo-real-time evaluation remains 2G, and production authority
remains none.
