# MacroPulse Model 1C v0.4.0

## Stable Labour Policy and Adaptive Shadow Tournament

This release converts the completed vintage stage metrics into a predeclared
15-decision point-forecast policy candidate and evaluates it against a strictly
prior-only adaptive shadow selector.

### Stable candidate map

- Payrolls: 12-month mean at month open; equal-weight ensemble after week 1;
  Bridge Ridge after week 2, month end, and pre-employment-report.
- Unemployment: equal-weight ensemble at all five stages.
- Earnings: Bridge Ridge at month open and after week 1; equal-weight ensemble
  after week 2, month end, and pre-employment-report.

### Main controls

- Adaptive shadow requires 24 previous common months.
- Rolling 36-month selection window.
- 3% robust-score switch hurdle.
- MAE, median-error, p90-tail, maximum-error, and directional-accuracy guards.
- Fixed-versus-shadow comparison on identical eligible months.
- Switching-stability and economic-regime diagnostics.
- Existing prior-only `exp_weighted_q80` interval diagnostics for both policies.

### Command

```cmd
python scripts\evaluate_labour_policy.py --backtest-id <BACKTEST_ID>
```

No FRED requests or vintage-backtest rerun are required. Model 1A and Model 1B
remain frozen at v1.0.0 production.
