# MacroPulse Model 1B v0.2.0.post2

Validation JSON serialization hotfix.

- Converts pandas MultiIndex tuple keys into deterministic string keys before JSON encoding.
- Fixes `TypeError: keys must be str, int, float, bool or None, not tuple`.
- Does not alter inflation forecasts, intervals, historical snapshots, or backtest results.
- The completed vintage backtest can be reused; no rerun is required.
