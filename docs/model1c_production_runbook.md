# Model 1C Production Runbook

```cmd
cd /d C:\Users\Cenk\OneDrive\MacroPulse
.venv\Scripts\activate
python scripts\download_labour_data.py
python scripts\run_labour_nowcast.py
python scripts\run_labour_operational_validation.py
```

Expected: Model 1C v1.0.0 production, three headlines, three shadow forecasts,
`exp_weighted_q80`, operational validation pass, and news residual <= 1e-8.
