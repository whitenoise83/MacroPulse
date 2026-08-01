# MacroPulse Model 1D v0.2.0.post1

## Scope

This hotfix corrects the Model 1D v0.2 historical integration-test fixture.

## Problem

The fixture inserted a synthetic GDP run into `forecast_registry` using the
non-existent column name `production_model_name`.

The actual MacroPulse schema uses `champion_model`.

## Fix

The fixture now inserts the same synthetic value into `champion_model`.

## Unchanged

- Model 1D historical reconstruction logic
- source selection and no-look-ahead rules
- scoring and regime classification
- database production tables
- dashboard
- production data

## Validation command

```cmd
python -m pytest -q tests\test_macro_state_history.py tests\test_macro_state_history_integration.py
```
