# MacroPulse Model 1C v0.2.0 — Vintage-Aware Labour Backtesting

Model 1C remains a separate development model. Model 1A GDP and Model 1B inflation remain frozen at v1.0.0 production.

## Why v0.2.0 is required

The v0.1.0 latest-revised benchmark works, but pandemic observations dominate its conventional metrics:

- PAYEMS maximum errors exceed 15 million jobs for several models.
- UNRATE maximum errors exceed 7 percentage points.
- Average-hourly-earnings maximum errors exceed 37 annualised percentage points.

Those values reflect the 2020 labour-market dislocation and composition effects. They make full-sample RMSE and directional accuracy unsuitable for choosing a production policy by themselves.

## Targets

- PAYEMS: monthly change in total nonfarm payroll employment, thousands of jobs.
- UNRATE: unemployment rate, percent.
- CES0500000003: monthly average-hourly-earnings growth, annualised percent.

## Predeclared forecast stages

- `month_open`
- `after_week_1`
- `after_week_2`
- `month_end`
- `pre_employment_report`

Each forecast cutoff must occur before the target's initial release date.

## Vintage evidence

v0.2.0 adds:

- historical ALFRED information sets;
- initial-release target outcomes;
- target-period leakage checks;
- future-observation checks;
- information-set hashes;
- robust p90 and maximum-error reporting;
- directional accuracy;
- pre-pandemic, pandemic-dislocation and post-2021 regime labels;
- development validation reports in `reports/labour_validation`.

Raw residual-based 80% intervals remain developmental. Later versions will calibrate uncertainty using prior forecast errors only.

## Commands

```cmd
python scripts\download_labour_data.py
python scripts\download_labour_initial_targets.py
python scripts\run_labour_vintage_backtest.py --start 2016-01
python scripts\run_labour_validation.py
streamlit run app.py
```

Use a smoke test before the full run:

```cmd
python -u scripts\run_labour_vintage_backtest.py --start 2022-01 --targets PAYEMS,UNRATE --stages month_end,pre_employment_report
```

The first full vintage run can take several hours because uncached historical snapshots must be downloaded. Cached snapshots are reused on later runs. Do not use `--refresh-snapshots` routinely.
