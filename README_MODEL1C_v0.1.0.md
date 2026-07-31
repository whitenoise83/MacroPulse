# MacroPulse Model 1C v0.1.0 — US Labour Nowcast Foundation

Model 1C is a separate development model. Model 1A GDP and Model 1B inflation remain frozen at v1.0.0 production.

## Targets

- PAYEMS: monthly change in total nonfarm payroll employment, thousands of jobs.
- UNRATE: unemployment rate, percent.
- CES0500000003: monthly average-hourly-earnings growth, annualised percent.

## Development models

- Labour AR(1)
- Labour 12-Month Mean
- Labour Bridge Ridge
- Labour Factor Ridge
- Labour Equal-Weight Ensemble

## Evidence status

The v0.1.0 backtest is chronological but uses latest-revised data and full-month feature values. It is an engineering benchmark, not pseudo-real-time validation evidence. Model 1C must not be presented as production-ready.

## Commands

```cmd
python scripts\download_labour_data.py
python scripts\run_labour_nowcast.py
python scripts\run_labour_backtest.py --start 2016-01
streamlit run app.py
```
