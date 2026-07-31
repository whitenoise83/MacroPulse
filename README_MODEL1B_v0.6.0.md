# MacroPulse Model 1B v0.6.0 — Governed Live Forecasting

Model 1B v0.6.0 converts the validated inflation candidate into a governed live
candidate without promoting it to production. Model 1A v1.0.0 is unchanged.

## Governed headline policy

| Target | Month open | Mid-month | Month end | Pre-release |
|---|---|---|---|---|
| Headline CPI | Ridge-AR Ensemble | Ridge-AR Ensemble | Ridge-AR Ensemble | Ridge-AR Ensemble |
| Core CPI | 12-Month Mean | Ridge-AR Ensemble | Ridge-AR Ensemble | Ridge-AR Ensemble |
| Headline PCE | Bridge Ridge | Bridge Ridge | Bridge Ridge | Bridge Ridge |
| Core PCE | Bridge Ridge | Ridge-AR Ensemble | Ridge-AR Ensemble | Ridge-AR Ensemble |

The adaptive selector is saved separately as a shadow challenger and cannot
replace the governed headline.

## What is added

- Automatic target-month and release-stage determination for all four targets.
- Historical release-lag estimation from stored initial vintages.
- Stable-policy headline selection.
- `exp_weighted_q80` live intervals from strictly earlier pseudo-real-time errors.
- Separate adaptive shadow forecasts and selector diagnostics.
- Governed live run, headline, component, and information-set tables in DuckDB.
- Configuration hash, code hash, information-set hash, model-state hash, Git commit,
  and a canonical SHA-256 governance signature.
- Exact path-dependent inflation news decomposition into:
  - revisions and removed observations;
  - newly released observations;
  - model-refit effects;
  - stable-policy changes;
  - arithmetic residual.
- Governed live operational validation and Markdown reports.
- Updated Inflation Nowcast page and a dedicated Inflation News page.

## Required prior evidence

The database must contain a passing Model 1B candidate-policy validation. The
validated record currently expected in the user's database is:

- Validation ID: `5f0cd6ea-c41f-44da-a21a-43490d8e75ce`
- Result: `PASS (28/28)`
- Backtest ID: `fdd2f573-a425-4abc-8056-f9843955bac2`

The live runner discovers the latest passing candidate-policy validation from
DuckDB; these identifiers are not hard-coded into the model.

## Installation

1. Stop Streamlit with `Ctrl+C`.
2. Extract the ZIP directly into `C:\Users\Cenk\OneDrive\MacroPulse`.
3. Choose **Replace the files in the destination**.
4. Do not delete `data\macropulse.duckdb`.

Run:

```cmd
cd /d C:\Users\Cenk\OneDrive\MacroPulse
.venv\Scripts\activate
pip install -e .
python scripts\initialise_database.py
```

Expected registration:

```text
Model registered: US_GDP_NOWCAST_1A v1.0.0 (production)
Model registered: US_INFLATION_NOWCAST_1B v0.6.0 (development)
```

## First governed live run

Refresh the current FRED dataset, then run Model 1B:

```cmd
python scripts\download_inflation_data.py
python scripts\run_inflation_nowcast.py
```

The first governed run normally reports:

```text
News decomposition: no_previous_run
```

That is expected because no earlier governed Model 1B run exists for comparison.
The forecast itself is still valid and registered.

## Operational validation

```cmd
python scripts\run_inflation_operational_validation.py
```

A healthy first run should finish with no failures or warnings. The exact number
of checks may increase in later patches, so rely on the status and failure count:

```text
Status: pass
Failed: 0
Warnings: 0
```

Reports are written to:

```text
reports\inflation_operational_validation\
```

## Inflation news decomposition

Every subsequent governed run automatically compares itself with the previous
run. After refreshing data on a later date, run:

```cmd
python scripts\download_inflation_data.py
python scripts\run_inflation_nowcast.py
python scripts\run_inflation_operational_validation.py
```

To rebuild attribution for the latest run without re-estimating the live forecast:

```cmd
python scripts\run_inflation_news.py
```

A target-month rollover is recorded as `target_roll`, because forecasts for two
different target months should not be interpreted as a news change.

## Dashboard

```cmd
streamlit run app.py
```

Use:

- **US Inflation Nowcast** for governed headlines, intervals, shadow forecasts,
  stages, and provenance hashes.
- **Inflation News** for new-data, revision, refit, and policy contributions.
- **Inflation Backtesting** for the historical candidate evidence.

## Governance status

v0.6.0 is a governed live candidate, not a production release. The remaining
steps are accumulation of live evidence, final freeze validation, freeze
assessment, explicit model-owner approval, and promotion to Model 1B v1.0.0.
