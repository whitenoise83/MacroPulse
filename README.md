# MacroPulse

## Model suite status

- **Model 1A — US GDP Nowcast:** production v1.0.0, frozen and validated.
- **Model 1B — US Inflation Nowcast:** development v0.2.0, vintage-aware validation foundation.

Model 1B now supports pseudo-real-time ALFRED reconstruction for headline/core CPI
and headline/core PCE at four predeclared monthly release stages. Model 1A's
approved production identity and policy are unchanged.

## Model 1B v0.2 workflow

Use CMD inside Visual Studio Code:

```cmd
cd /d C:\Users\Cenk\OneDrive\MacroPulse
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
python scripts\initialise_database.py
```

Download current inflation data and the target initial-release history:

```cmd
python scripts\download_inflation_data.py
python scripts\download_inflation_initial_targets.py
```

Run a smaller live-API smoke test first:

```cmd
python scripts\run_inflation_vintage_backtest.py --start 2022-01 --targets CPILFESL,PCEPILFE --stages month_end,pre_release
```

Then run the full development validation sample:

```cmd
python scripts\run_inflation_vintage_backtest.py --start 2015-01
python scripts\run_inflation_validation.py
```

The four forecast stages are:

- `month_open`
- `mid_month`
- `month_end`
- `pre_release`

Every historical forecast uses an ALFRED snapshot dated at the declared cutoff.
The realised target is reconstructed from the target index's initial-release
snapshot. Target-month observations are rejected if they appear before their
initial release.

## Current Model 1B models

Each inflation target currently includes:

- Inflation AR(1)
- Inflation 12-Month Mean
- Inflation Bridge Ridge
- Inflation Ridge-AR Ensemble

These remain development benchmarks. v0.2 validates the data and timing
architecture; it does not freeze a production model.

## Dashboard

```cmd
streamlit run app.py
```

Open:

- US Inflation Nowcast
- Inflation Backtesting

The Inflation Backtesting page separates pseudo-real-time vintage evidence from
the older latest-revised engineering benchmark.

## Model 1A governance

Model 1A remains `US_GDP_NOWCAST_1A v1.0.0` in production. Model 1B changes must
not alter its approved configuration hash, code hash, stage policy, or approval
record.
