# MacroPulse

## Model suite status

- **Model 1A — US GDP Nowcast:** production v1.0.0, frozen and validated.
- **Model 1B — US Inflation Nowcast:** production v1.0.0, frozen and validated.
- **Model 1C — US Labour Nowcast:** development v0.4.0 stable-policy tournament.

Model 1B provides governed monthly forecasts for headline/core CPI and
headline/core PCE. Forecasts are monthly log changes annualised by multiplying
by 1,200.

## Model 1B production policy

- Headline CPI: Ridge-AR Ensemble at all four forecast stages.
- Core CPI: 12-Month Mean at month open; Ridge-AR Ensemble thereafter.
- Headline PCE: Bridge Ridge at all four forecast stages.
- Core PCE: Bridge Ridge at month open; Ridge-AR Ensemble thereafter.
- Production interval method: `exp_weighted_q80` using strictly prior errors.
- Adaptive model selection: shadow challenger only.

## Production workflow

Use CMD inside Visual Studio Code:

```cmd
cd /d C:\Users\Cenk\OneDrive\MacroPulse
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
python scripts\initialise_database.py
python scripts\promote_model1b_v1.py
```

Refresh data and run the governed production forecast:

```cmd
python scripts\download_inflation_data.py
python scripts\run_inflation_nowcast.py
python scripts\run_inflation_operational_validation.py
```

Open the application:

```cmd
streamlit run app.py
```

The production promotion script verifies the complete approved evidence chain:

- candidate validation `5f0cd6ea-c41f-44da-a21a-43490d8e75ce` — 28/28 passed;
- governed-live operational validation `58c89931-0f6b-43ed-8815-abbc99fa4ac8` — 20/20 passed;
- freeze assessment `2b7fe987-384a-451b-971f-03d5bf5106c7` — 14/14 passed;
- governed live run `905deade-2bbf-4c89-801e-ce296bb00d97`.


## Model 1C vintage-aware development

Model 1C forecasts monthly nonfarm payroll change, the unemployment rate, and
average-hourly-earnings growth. Version 0.4.0 contains a completed vintage
backtest, prior-only `exp_weighted_q80` intervals, a stable 15-decision policy
candidate, and a prior-only adaptive shadow challenger. It is not production
approved.

```cmd
python scripts\evaluate_labour_policy.py --backtest-id 834e0655-ba81-4b96-b42c-e1cdda73b847
```

## Governance

Model 1A and Model 1B are separate production models. Changes to one model must
not alter the other model's approved policy, version, hashes, validation history,
or approval record. Material changes require challenger evidence, a new version,
revalidation, and explicit model-owner approval.
