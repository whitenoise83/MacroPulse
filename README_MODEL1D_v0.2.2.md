# MacroPulse Model 1D v0.2.2

Model 1D v0.2.2 adds a diagnostic layer over the validated v0.2.1
production-lineage historical reconstruction.

## Coverage diagnostics

The new diagnostic command distinguishes requested-window coverage from the
effective common source window. It identifies every missing month and the exact
required target or stable-policy model that is unavailable.

October 2025 remains missing because the approved source backtests do not
contain all eight governed inputs. The observed missing targets are:

- CPIAUCSL
- CPILFESL
- UNRATE

No interpolation, alternate-target substitution, or alternate-model
substitution is performed.

## Joint uncertainty candidate

The existing rectangular possible-regime set is retained. v0.2.2 adds a
separate deterministic Gaussian-copula diagnostic using the configured score
correlation matrix and marginal 80% intervals.

Outputs include the top regime probability, normalized entropy, effective
number of regimes, material regime count, and the full probability
distribution. This remains a research diagnostic, not a validated probability
model.

## Transition diagnostics

Transitions are reported with raw counts and the number of originating-regime
observations. Non-contiguous months are excluded. A minimum-sample indicator
prevents small-sample probabilities from being presented without context.
