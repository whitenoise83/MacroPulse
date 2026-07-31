# Model 1C — US Labour Market Nowcast Engine (Draft Model Card)

## Purpose

Provide monthly forecasts for nonfarm payroll change, unemployment, and wage growth as a third pillar of the MacroPulse unified macro state.

## Current version

v0.1.0 development foundation.

## Inputs

FRED-hosted BLS, Department of Labor, and Federal Reserve economic series covering claims, labour utilisation, JOLTS, temporary help, hours, manufacturing employment, and industrial production.

## Outputs

Five development model forecasts for each target, with preliminary 80% residual-based intervals.

## Known limitations

- Uses latest-revised data rather than historical information sets.
- Current-period weekly data are aggregated to a monthly mean without release-stage modelling.
- JOLTS and other delayed series may be carried forward within the configured freshness limit.
- No production model policy has been selected.
- No prior-only interval calibration or news decomposition exists yet.

## Next validation stage

v0.2.0 will introduce historical vintages, initial-release outcomes, employment-report cutoffs, release-stage backtesting, and no-look-ahead controls.
