# MacroPulse Model 1B v0.4.1 — Common-Sample Policy Verification

This overlay corrects an interpretation gap in v0.4.0: the fixed policy used all
available months while the adaptive shadow could only operate after its prior-only
warm-up. v0.4.1 compares both policies on identical eligible months.

It also records `exp_weighted_q80` as the development interval candidate based on
the predeclared interval-score tournament. It remains subject to stage-level
validation and is not a production interval.

No FRED download or vintage backtest rerun is required.
