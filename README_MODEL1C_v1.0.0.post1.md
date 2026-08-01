# MacroPulse Model 1C v1.0.0.post1 — Operational Metadata Repair

## Problem

The Model 1C governed-live operational validation passed 20/20 checks, but its
DuckDB row was persisted with three metadata fields in DataFrame order rather
than table order:

- `backtest_id` received the model ID
- `model_id` received the model version
- `model_version` received the backtest ID

Forecasts, checks, hashes, reports, the governed live run, candidate validation,
and freeze assessment were not altered.

## Repair

```cmd
python scripts\repair_labour_operational_validation_metadata.py ^
  --validation-id f535fdc2-c75c-4da8-a0f8-e3d1b80416f3

python scripts\promote_model1c_v1.py
```

The repair only runs when the row exactly matches the recognized three-column
legacy shift and the linked live run confirms the correct values.

## Prevention

`operational_validation.py` now reorders validation-run and validation-check
columns explicitly before inserting them into DuckDB. The promotion command
also invokes the safe idempotent repair before verifying the evidence chain.
