# MacroPulse Model 1A — GDP Production Freeze Assessment

- Model: `US_GDP_NOWCAST_1A`
- Candidate version: `0.6.0`
- Lifecycle: `freeze_candidate`
- Validation ID: `bf5b32c2-dc61-4742-8634-27e204218987`
- Validation status: **CONDITIONAL**
- Freeze readiness: **CONDITIONAL_OWNER_REVIEW**
- Governed live forecast for this version: **YES**
- Configuration hash: `56a48721ee27eaadbcab95c93c032bedd5caa8350ad22c2dcfbe29a872095617`
- Code hash: `98804823bcfe643be669b02ac96d61a3b740fbf2b05b85131a12823f64e85300`

## Automated gates

| gate_name | check_name | status | observed_value | threshold |
|---|---|---|---|---|
| Data integrity | One forecast per model, stage, and target quarter | pass | 0 duplicate rows | 0 duplicate rows |
| Econometric validity | Champion RMSE relative to Bridge benchmark | pass | 0.72274 | <= 1.020 |
| Econometric validity | Champion is not materially worse than Bridge at any stage | pass | 0.988425 | <= 1.100 |
| Econometric validity | Champion performance is reported for all declared economic regimes | pass | 0 stages with missing regime results | 0 missing stage/regime combinations |
| Econometric validity | Forecast dates match pre-declared stage rules | pass | 0 mismatches | 0 mismatches |
| Econometric validity | Interval calibration uses prior forecast errors only | pass | 0 violations | 0 violations |
| Econometric validity | Minimum evaluated quarters at every forecast stage | pass | 45 | >= 20 |
| Econometric validity | No observation is dated after its information cutoff | pass | 0 future-dated observations | 0 future-dated observations |
| Econometric validity | Outcome release occurs after forecast cutoff | pass | 0 violations | 0 violations |
| Econometric validity | Rolling ensemble weights use prior quarters only | pass | 0 violations | 0 violations |
| Econometric validity | Stage-adaptive champion follows the pre-declared selection policy | pass | 0 violations | 0 violations |
| Econometric validity | Stage-adaptive champion selection uses prior quarters only | pass | 0 violations | 0 violations |
| Econometric validity | Target-quarter GDP is absent from forecast information sets | pass | 0 leaked snapshots | 0 leaked snapshots |
| Operational reliability | DFM estimation failure rate | pass | 0 | <= 10% |
| Operational reliability | News attribution residual is immaterial | pass | 0 | <= 0.01 pp |
| Operational reliability | News decomposition arithmetic closes | pass | 0 | <= 1e-06 |
| Reproducibility | At least one live forecast has a governance signature | warning | run the live nowcast after installing v0.6 | at least one record |
| Reproducibility | Every forecast has a valid information-set hash | pass | 0 invalid hashes | 0 invalid hashes |
| Reproducibility | Model version is registered | pass | registered | registered |
| Uncertainty calibration | Champion coverage is statistically acceptable at every stage | pass | {"early_quarter": {"coverage": 0.8444, "p_value": 0.576986}, "after_month_1": {"coverage": 0.8889, "p_value": 0.189658}, "after_month_2": {"coverage": 0.8444, "p_value": 0.576986}, "quarter_end": {"coverage": 0.8444, "p_value": 0.576986}, "pre_advance_release": {"coverage": 0.8667, "p_value": 0.350936}} | exact binomial p-value >= 0.05 at every stage |
| Uncertainty calibration | Champion coverage is statistically consistent with the target | warning | {"coverage": 0.8578, "p_value": 0.030034, "wilson_95_ci": [0.8061, 0.8974]} | exact binomial p-value >= 0.05 |
| Uncertainty calibration | Champion interval score relative to Bridge benchmark | pass | 0.778502 | <= 1.100 |

## Stage-Adaptive Champion metrics

| forecast_stage | observations | rmse | mae | median_ae | bias | interval_coverage | average_interval_width | interval_score_80 |
|---|---|---|---|---|---|---|---|---|
| early_quarter | 45 | 6.1851 | 2.5046 | 0.9151 | 0.7498 | 0.8444 | 5.8424 | 19.2078 |
| after_month_1 | 45 | 7.0956 | 2.7218 | 0.9051 | -0.644 | 0.8889 | 6.8865 | 20.2195 |
| after_month_2 | 45 | 2.778 | 1.8466 | 1.0512 | 0.421 | 0.8444 | 7.2888 | 12.016 |
| quarter_end | 45 | 2.719 | 1.8156 | 1.0852 | 0.7079 | 0.8444 | 6.8781 | 11.8829 |
| pre_advance_release | 45 | 4.2154 | 2.1193 | 0.9757 | 0.9193 | 0.8667 | 6.5091 | 14.9614 |

## Selected components

| forecast_stage | selected_component | forecasts |
|---|---|---|
| after_month_1 | Bridge–DFM Ensemble | 16 |
| after_month_1 | Dynamic Factor Model | 24 |
| after_month_1 | Rolling Bridge–DFM Ensemble | 5 |
| after_month_2 | Bridge–DFM Ensemble | 31 |
| after_month_2 | Dynamic Factor Model | 14 |
| early_quarter | Bridge–DFM Ensemble | 8 |
| early_quarter | Dynamic Factor Model | 37 |
| pre_advance_release | Bridge Ridge | 1 |
| pre_advance_release | Bridge–DFM Ensemble | 18 |
| pre_advance_release | Dynamic Factor Model | 22 |
| pre_advance_release | Rolling Bridge–DFM Ensemble | 4 |
| quarter_end | Bridge Ridge | 9 |
| quarter_end | Bridge–DFM Ensemble | 19 |
| quarter_end | Dynamic Factor Model | 3 |
| quarter_end | Rolling Bridge–DFM Ensemble | 14 |

## Regime robustness

| forecast_stage | sample | observations | rmse | trimmed_rmse_10 | mae | max_abs_error | interval_coverage | average_interval_width |
|---|---|---|---|---|---|---|---|---|
| early_quarter | Full sample | 45 | 6.1851 | 1.5869 | 2.5046 | 34.3116 | 0.8444 | 5.8424 |
| early_quarter | Pre-pandemic (through 2019Q4) | 20 | 1.1297 | 0.8288 | 0.8655 | 3.1125 | 0.95 | 3.9008 |
| early_quarter | Pandemic (2020Q1–2021Q2) | 6 | 16.4228 | 16.4228 | 11.3748 | 34.3116 | 0.3333 | 3.8804 |
| early_quarter | Post-pandemic (from 2021Q3) | 19 | 2.0222 | 1.7725 | 1.4288 | 4.5981 | 0.8947 | 8.5056 |
| early_quarter | Last 20 quarters | 20 | 2.0539 | 1.5493 | 1.4865 | 4.5981 | 0.9 | 8.4433 |
| after_month_1 | Full sample | 45 | 7.0956 | 1.8191 | 2.7218 | 43.7272 | 0.8889 | 6.8865 |
| after_month_1 | Pre-pandemic (through 2019Q4) | 20 | 1.0969 | 0.9248 | 0.8505 | 2.1407 | 1.0 | 4.1888 |
| after_month_1 | Pandemic (2020Q1–2021Q2) | 6 | 18.903 | 18.903 | 12.2307 | 43.7272 | 0.3333 | 6.0408 |
| after_month_1 | Post-pandemic (from 2021Q3) | 19 | 2.2666 | 1.9671 | 1.6889 | 5.2884 | 0.9474 | 9.9933 |
| after_month_1 | Last 20 quarters | 20 | 2.2707 | 1.7864 | 1.7217 | 5.2884 | 0.95 | 10.0008 |
| after_month_2 | Full sample | 45 | 2.778 | 1.8251 | 1.8466 | 7.6631 | 0.8444 | 7.2888 |
| after_month_2 | Pre-pandemic (through 2019Q4) | 20 | 1.1773 | 0.9875 | 0.998 | 2.2865 | 0.9 | 3.9052 |
| after_month_2 | Pandemic (2020Q1–2021Q2) | 6 | 5.5787 | 5.5787 | 4.891 | 7.6631 | 0.3333 | 6.3386 |
| after_month_2 | Post-pandemic (from 2021Q3) | 19 | 2.644 | 2.031 | 1.7784 | 7.6539 | 0.9474 | 11.1506 |
| after_month_2 | Last 20 quarters | 20 | 2.6033 | 1.7077 | 1.7718 | 7.6539 | 0.95 | 11.1507 |
| quarter_end | Full sample | 45 | 2.719 | 1.6996 | 1.8156 | 8.2106 | 0.8444 | 6.8781 |
| quarter_end | Pre-pandemic (through 2019Q4) | 20 | 1.0345 | 0.882 | 0.9001 | 2.1659 | 0.95 | 3.6825 |
| quarter_end | Pandemic (2020Q1–2021Q2) | 6 | 5.1003 | 5.1003 | 4.4455 | 7.444 | 0.3333 | 4.4204 |
| quarter_end | Post-pandemic (from 2021Q3) | 19 | 2.8581 | 2.2084 | 1.9487 | 8.2106 | 0.8947 | 11.0179 |
| quarter_end | Last 20 quarters | 20 | 2.8081 | 1.7323 | 1.9305 | 8.2106 | 0.9 | 10.7981 |
| pre_advance_release | Full sample | 45 | 4.2154 | 1.6479 | 2.1193 | 23.1846 | 0.8667 | 6.5091 |
| pre_advance_release | Pre-pandemic (through 2019Q4) | 20 | 0.9795 | 0.8583 | 0.8714 | 1.9619 | 1.0 | 3.6171 |
| pre_advance_release | Pandemic (2020Q1–2021Q2) | 6 | 10.5841 | 10.5841 | 7.6602 | 23.1846 | 0.3333 | 4.6108 |
| pre_advance_release | Post-pandemic (from 2021Q3) | 19 | 2.3873 | 1.9191 | 1.6831 | 6.4802 | 0.8947 | 10.1528 |
| pre_advance_release | Last 20 quarters | 20 | 2.3571 | 1.7024 | 1.6831 | 6.4802 | 0.9 | 10.0353 |

## Model-owner decision

- [ ] Review every warning and record the decision.
- [ ] Confirm the stage-adaptive fallback hierarchy.
- [ ] Confirm the 80% interval method and revalidation triggers.
- [ ] Confirm that the live dashboard and news decomposition use the same production forecast.
- [ ] Approve promotion to `US_GDP_NOWCAST_1A v1.0.0`.

Promotion is a manual governance action. This script never changes the model version automatically.
