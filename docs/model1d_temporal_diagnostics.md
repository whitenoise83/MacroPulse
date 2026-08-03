# Model 1D v0.3.2 temporal diagnostics

## Research question

Does Model 1D add value by detecting macro-regime turning points more accurately
or earlier than a naive persistence rule?

## Source specification

The source specification is the latest successful v0.3.1 rolling-origin
research leader. Its v0.3.1 promotion gate remains failed. v0.3.2 does not use
the consumed audit to choose normalization, weights, thresholds, or uncertainty.

## Temporal rules

### Raw monthly

Uses the deterministic point-regime classification each month.

### Hysteresis thresholds

Retains the previous decision unless the new raw regime has both the configured
minimum probability and the configured probability advantage over the previous
regime.

### One-month confirmation

Requires the same alternative raw regime in two consecutive complete months
before switching.

### Persistence prior

Combines the current regime probability distribution with an explicit prior on
the previous decision, then chooses the posterior maximum.

All rules reset after a non-contiguous evidence gap.

## Transition matching

An actual transition is matched to an unassigned predicted transition when the
new regime agrees and the predicted date falls within the configured plus or
minus two-month window. Negative lead/lag values indicate early detection;
positive values indicate late detection.

## Governance

The temporal research leader must beat the strongest naive baseline in most
folds, achieve acceptable family accuracy and transition recall, avoid excessive
false transitions and regime collapse, and have a strictly positive lower
bootstrap margin. Passing these diagnostics would still not approve a candidate.
