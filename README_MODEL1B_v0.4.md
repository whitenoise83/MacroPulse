# MacroPulse Model 1B v0.4.0

This patch evaluates a stable target-stage inflation point-forecast policy,
a prior-only shadow selector, and four predeclared prior-only interval methods.
It reuses an existing completed vintage backtest and makes no FRED requests.

## Install

Extract into the MacroPulse project root and replace matching files, then run:

```cmd
cd /d C:\Users\Cenk\OneDrive\MacroPulse
.venv\Scripts\activate
pip install -e .
python scripts\initialise_database.py
python scripts\evaluate_inflation_policy.py --backtest-id fdd2f573-a425-4abc-8056-f9843955bac2
```

Model 1A v1.0.0 is not modified.
