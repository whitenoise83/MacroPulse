# MacroPulse Model 1C v0.4.0.post1

## Labour policy interval merge hotfix

This narrow update fixes the Model 1C policy tournament crash:

```text
KeyError: "Column(s) ['interval_covered'] do not exist"
```

Vintage backtest policy rows already contain raw residual-based interval fields.
The prior-only calibration table contains fields with the same names. Pandas
therefore added `_x` and `_y` suffixes during the merge, leaving no canonical
`interval_covered` column for the interval summary.

The hotfix removes the superseded raw interval fields before attaching the
validated prior-only `exp_weighted_q80` intervals. Point forecasts, stable policy
decisions, adaptive-shadow selections, the completed vintage backtest, and the
existing interval calibration are unchanged.

No FRED download or vintage backtest rerun is required.
