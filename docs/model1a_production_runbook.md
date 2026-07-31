# Model 1A Production Runbook

## Approved version

- Model: `US_GDP_NOWCAST_1A`
- Version: `1.0.0`
- Lifecycle: `production`
- Validation source version: `0.6.1`
- Approved validation ID: `7ee34d06-f393-4fb7-90ef-6239758f8503`

## Standard run

From CMD in the project root:

```cmd
.venv\Scripts\activate
python scripts\download_fred_data.py
python scripts\run_dfm_nowcast.py
```

Open the dashboard:

```cmd
streamlit run app.py
```

## Routine verification

```cmd
python scripts\run_validation.py
```

Confirm:

- status is `pass` or only contains a documented live-registration warning before
  the first v1.0.0 run;
- current model registry version is `1.0.0` and lifecycle is `production`;
- information-set, configuration, and code hashes are recorded;
- DFM diagnostics are visible;
- news decomposition closes arithmetically;
- production component matches the approved stage map.

## Fallbacks

- DFM failure -> Bridge Ridge
- materially stale required data -> Bridge Ridge
- insufficient rolling history -> declared stable stage component or configured
  fixed fallback
- news attribution failure -> forecast remains visible, attribution is marked failed

## Revalidation triggers

- any look-ahead audit failure;
- DFM failure rate above 10%;
- production RMSE or MAE above the best eligible static model by more than 10%
  at any stage;
- production upper-tail error above the coherent accuracy-eligible comparator by
  more than 20%;
- stage-level interval coverage statistically inconsistent with 80%;
- material data-definition or transformation change;
- two consecutive quarters with absolute forecast error above 5 percentage points.

## Change control

Do not edit the v1.0.0 production specification in place. Create a challenger
version, preserve v1.0.0 forecasts, rerun pseudo-real-time validation, document
changes, and obtain explicit model-owner approval.
