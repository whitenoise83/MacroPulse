# MacroPulse Model 1B v0.4.0

## Stable Policy and Shadow-Selection Research

- Declares a stable target-stage point-forecast policy candidate from the completed vintage evidence.
- Keeps the policy in development status; no production promotion is performed.
- Adds a prior-only robust shadow selector with a 24-error warm-up, 36-month window, 2% switch hurdle, and MAE/tail/maximum-error guards.
- Adds a predeclared prior-only interval-method tournament for the selected policy rows:
  - rolling 80th-percentile absolute error;
  - exponentially weighted 80th-percentile absolute error;
  - target-shrunk 80th-percentile absolute error;
  - exponentially weighted Gaussian scale.
- Evaluates interval methods with coverage, width, and interval score.
- Reuses the existing vintage backtest and cached ALFRED snapshots; no FRED calls are required.
- Leaves Model 1A v1.0.0 untouched.
