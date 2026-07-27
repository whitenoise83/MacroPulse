# MacroPulse

Phase 1 of MacroPulse provides:

- a FRED data connector;
- current-value and initial-release storage;
- a DuckDB macro data warehouse;
- a transformation registry;
- a US real-GDP bridge model;
- an AR(1) benchmark;
- a simple forecast ensemble;
- a Streamlit dashboard.

## Windows CMD setup

```cmd
cd /d C:\Users\Cenk\OneDrive\MacroPulse

py -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

copy .env.example .env
```

Open `.env` and replace the placeholder with your FRED API key.

Then run:

```cmd
python scripts\initialise_database.py
python scripts\download_fred_data.py
python scripts\run_baseline_nowcast.py
streamlit run app.py
```

## Notes

The Phase 1 uncertainty interval is an empirical model-residual interval, not a
fully Bayesian density forecast. The later Dynamic Factor Model and
pseudo-real-time backtesting modules will replace this with stronger uncertainty
and release-news decomposition.
