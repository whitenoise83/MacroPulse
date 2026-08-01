# MacroPulse Model 1D v0.1.0.post1 — Integration-Test Fixture Hotfix

## Problem

The Model 1D integration-test fixture attempted to insert 23 values into
`labour_live_forecasts` using 24 SQL placeholders.

This prevented the test from reaching the Model 1D engine.

## Fix

The fixture now:

- names all 23 `labour_live_forecasts` columns explicitly;
- uses exactly 23 placeholders;
- preserves the same synthetic labour values;
- does not change Model 1D scoring, source selection, persistence, configuration,
  or dashboard code.

## Run

```cmd
python -m pytest -q tests\test_macro_state_engine.py tests\test_macro_state_identity.py tests\test_macro_state_integration.py
```
