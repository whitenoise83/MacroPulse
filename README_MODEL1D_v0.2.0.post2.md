# MacroPulse Model 1D v0.2.0.post2

## Defect

`regime_durations()` grouped historical states by:

- `segment`
- `primary_regime`
- `primary_regime_label`

It then used `reset_index(drop=True)`, which discarded all three grouping
columns. Persistence subsequently failed because the duration table no longer
contained `primary_regime` or `primary_regime_label`.

## Fix

The function now:

1. groups with `as_index=False`;
2. preserves `primary_regime` and `primary_regime_label`;
3. removes only the internal `segment` identifier;
4. returns the exact schema required by `save_macro_state_history()`.

A regression test now asserts that both regime columns survive duration
aggregation.

## Unchanged

- source-run selection
- no-look-ahead logic
- score construction
- uncertainty envelope
- regime classification
- transition matrix
- live Model 1D state logic
