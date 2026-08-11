# Model 2B.1 — Data & Vintage Architecture

## Purpose

This workstream starts from Model 2A commit `4033a8f88fa5ffc0bb749ab17621ab6e82074ec6` and builds the read-only
historical-vintage audit layer for the Bayesian VAR. It does not estimate a BVAR
and does not choose an estimation sample.

## Quarterly information set

The BVAR estimation panel is a complete-quarter joint panel.

| Series | Rule |
|---|---|
| GDPC1 | native quarterly observation |
| PCEPILFE | quarter-end month must be present |
| UNRATE | quarter-end month must be present; use the observed quarter-end unemployment rate |
| FEDFUNDS | all three monthly observations required, then mean |

Transformations:

```text
GDP growth       = 400 * Δ log(GDPC1)
Core PCE infl.   = 400 * Δ log(quarter-end PCEPILFE)
Unemployment     = quarter-end UNRATE, level
Policy rate      = three-month quarterly mean, level
```

## Why unemployment is quarter-end rather than quarterly average

The vintage audit identified one structural break in the otherwise continuous
joint panel: 2025Q4. The cause is not a cache failure. October 2025 household
survey data were not collected during the federal appropriations lapse, so an
October unemployment-rate observation does not exist and was not reconstructed
retroactively.

For Model 2, UNRATE is therefore defined consistently over the full sample as a
**quarter-end stock variable**, not a quarterly average. This uses an observed
monthly unemployment rate and does not fill, interpolate, or infer the missing
October 2025 observation.

This rule must be applied to every quarter, not only 2025Q4.

FEDFUNDS remains a quarterly mean because its monthly observations are available
and the quarterly average is the intended policy-rate exposure measure.

## No-look-ahead rules

The builder rejects any row whose observation date is later than the requested
as-of date. It never substitutes the latest vintage when an exact historical
snapshot is absent.

For quarter-end series, the quarter is unavailable until that quarter's final
month observation exists in the exact vintage. For FEDFUNDS, all three months
must exist. No unavailable value is imputed.

## Current-quarter interface

The historical estimation panel stops at the latest fully observed joint
quarter. Model 1A/1B/1C current-state outputs are not spliced into historical
data in 2B.1.

The governed Model 1 current-state anchor remains a separate 2B design problem.

## Audit output

The audit reports cached common as-of dates, raw row counts, first/last usable
transformed quarter, complete joint quarters, lag between the cutoff and latest
complete quarter, and missing-series diagnostics.

No result from this audit changes the Model 2A prior family, lag grid,
shrinkage grid, variable ordering, or forecast horizons.

## Next gate

2B.1 ends with a factual inventory of historical-vintage coverage. 2B.2 freezes
the pseudo-real-time origin grid, admissible estimation/evaluation dates, any
required historical snapshot acquisition, and the governed Model 1
current-state anchor.


## Release-guard maintenance

The Phase III release verifiers now validate the immutable `phase3-evaluation-v1.0.1` tag/commit rather than treating a later roadmap descendant HEAD as the release itself. The current checkout must separately descend from that immutable release.

This maintenance changes no Phase III release file, manifest, evaluation semantics, model specification, or immutable tag.
