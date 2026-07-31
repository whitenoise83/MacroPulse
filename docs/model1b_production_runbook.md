# Model 1B Production Runbook

## Routine run

```cmd
cd /d C:\Users\Cenk\OneDrive\MacroPulse
.venv\Scripts\activate
python scripts\download_inflation_data.py
python scripts\run_inflation_nowcast.py
python scripts\run_inflation_operational_validation.py
```

## Expected status

- Model: `US_INFLATION_NOWCAST_1B v1.0.0 (production)`
- Four production headline forecasts
- Four separately stored adaptive shadow forecasts
- Interval method: `exp_weighted_q80`
- Operational validation: pass with no failures or warnings
- News reconciliation residual: no greater than `1e-8`

## Failure handling

Do not overwrite or delete previous live runs. Preserve the failed run and its
provenance information. Investigate data freshness, FRED availability, release
stage, target leakage, policy compliance, interval history, hashes, and news
reconciliation before rerunning.

## Change control

Do not edit the stable map, interval method, predictor definitions, transforms,
or release-stage rules directly in production. Develop and validate a new
version as a challenger.
