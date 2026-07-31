# MacroPulse Model 1A - GDP Production Freeze Assessment

- Model: `US_GDP_NOWCAST_1A`
- Candidate version: `0.6.1`
- Lifecycle: `freeze_candidate`
- Production policy: `Stable Stage Policy`
- Shadow challenger: `Robust Stage-Adaptive Policy`
- Validation ID: `4cfec0e5-ce76-43ba-80ed-ec293e60144a`
- Validation status: **FAIL**
- Freeze readiness: **NOT_READY**
- Governed live forecast for this version: **YES**
- Configuration hash: `35a64b681d056961ede40377c8e6eacbb77420805fb477a4804c50fa39f2ab54`
- Code hash: `25930e0a96a431899236625ef8678f0e7665fc146e06f015395e0ba3d0dd617d`

## Automated gates

| gate_name | check_name | status | observed_value | threshold |
|---|---|---|---|---|
| Data integrity | One forecast per model, stage, and target quarter | pass | 0 duplicate rows | 0 duplicate rows |
| Econometric validity | Forecast dates match pre-declared stage rules | pass | 0 mismatches | 0 mismatches |
| Econometric validity | Interval calibration uses prior forecast errors only | pass | 0 violations | 0 violations |
| Econometric validity | Minimum evaluated quarters at every forecast stage | pass | 45 | >= 20 |
| Econometric validity | No observation is dated after its information cutoff | pass | 0 future-dated observations | 0 future-dated observations |
| Econometric validity | Outcome release occurs after forecast cutoff | pass | 0 violations | 0 violations |
| Econometric validity | Production MAE is competitive with the best static model at every stage | pass | 1 | <= 1.100 |
| Econometric validity | Production RMSE is competitive with the best static model at every stage | pass | 1 | <= 1.100 |
| Econometric validity | Production RMSE relative to Bridge benchmark | pass | 0.593491 | <= 1.020 |
| Econometric validity | Production maximum error is not materially worse at any stage | pass | 1 | <= 1.250 |
| Econometric validity | Production performance is reported for all declared economic regimes | pass | 0 stages with missing regime results | 0 missing stage/regime combinations |
| Econometric validity | Production upper-tail error is competitive at every stage | fail | 1.486 | <= 1.200 |
| Econometric validity | Robust shadow selection uses prior quarters only | pass | 0 violations | 0 violations |
| Econometric validity | Robust shadow selector follows prior-only switching rules | pass | 0 violations | 0 violations |
| Econometric validity | Robust shadow selector has acceptable switching stability | pass | 4 | <= 6 switches per stage |
| Econometric validity | Rolling ensemble weights use prior quarters only | pass | 0 violations | 0 violations |
| Econometric validity | Stable stage policy follows the pre-declared component map | pass | 0 violations | 0 violations |
| Econometric validity | Target-quarter GDP is absent from forecast information sets | pass | 0 leaked snapshots | 0 leaked snapshots |
| Operational reliability | DFM estimation failure rate | pass | 0 | <= 10% |
| Operational reliability | News attribution residual is immaterial | pass | 0 | <= 0.01 pp |
| Operational reliability | News decomposition arithmetic closes | pass | 2.22045e-16 | <= 1e-06 |
| Reproducibility | At least one live forecast has a governance signature | pass | available | at least one record |
| Reproducibility | Every forecast has a valid information-set hash | pass | 0 invalid hashes | 0 invalid hashes |
| Reproducibility | Model version is registered | pass | registered | registered |
| Uncertainty calibration | Production coverage is cluster-consistent with the target | pass | {"coverage": 0.8578, "cluster_bootstrap_p_value": 0.193361, "bootstrap_95_ci": [0.7644, 0.9378], "quarters": 45, "forecasts": 225} | target-quarter clustered bootstrap p-value >= 0.05 |
| Uncertainty calibration | Production coverage is statistically acceptable at every stage | pass | {"early_quarter": {"coverage": 0.8444, "p_value": 0.576986}, "after_month_1": {"coverage": 0.8667, "p_value": 0.350936}, "after_month_2": {"coverage": 0.8667, "p_value": 0.350936}, "quarter_end": {"coverage": 0.8444, "p_value": 0.576986}, "pre_advance_release": {"coverage": 0.8667, "p_value": 0.350936}} | exact stage-level binomial p-value >= 0.05 |
| Uncertainty calibration | Production interval score relative to Bridge benchmark | pass | 0.708914 | <= 1.100 |

## Stable production policy metrics

| forecast_stage | observations | rmse | trimmed_rmse_10 | mae | p90_abs_error | max_abs_error | interval_coverage | average_interval_width | interval_score_80 |
|---|---|---|---|---|---|---|---|---|---|
| early_quarter | 45 | 6.1835 | 1.5801 | 2.4964 | 4.136 | 34.3116 | 0.8444 | 5.9211 | 19.2128 |
| after_month_1 | 45 | 4.5461 | 1.8175 | 2.2786 | 4.7261 | 24.0144 | 0.8667 | 6.8201 | 15.9578 |
| after_month_2 | 45 | 2.7593 | 1.8396 | 1.8585 | 5.3245 | 7.6539 | 0.8667 | 7.2677 | 11.9552 |
| quarter_end | 45 | 2.6859 | 1.7092 | 1.809 | 4.7365 | 8.0669 | 0.8444 | 6.5239 | 11.3641 |
| pre_advance_release | 45 | 2.8613 | 1.7836 | 1.8622 | 5.01 | 8.7948 | 0.8667 | 7.4437 | 12.7999 |

## Robust adaptive shadow metrics

| forecast_stage | observations | rmse | mae | p90_abs_error | max_abs_error | interval_coverage |
|---|---|---|---|---|---|---|
| early_quarter | 45 | 6.1835 | 2.4964 | 4.136 | 34.3116 | 0.8444 |
| after_month_1 | 45 | 4.5461 | 2.2786 | 4.7261 | 24.0144 | 0.8667 |
| after_month_2 | 45 | 2.7593 | 1.8585 | 5.3245 | 7.6539 | 0.8667 |
| quarter_end | 45 | 2.7414 | 1.8594 | 4.879 | 8.2106 | 0.8444 |
| pre_advance_release | 45 | 4.376 | 2.1471 | 4.0107 | 23.1846 | 0.8444 |

## Stable policy components

| forecast_stage | selected_component | forecasts |
|---|---|---|
| after_month_1 | Dynamic Factor Model | 45 |
| after_month_2 | Bridge–DFM Ensemble | 45 |
| early_quarter | Dynamic Factor Model | 45 |
| pre_advance_release | Dynamic Factor Model | 45 |
| quarter_end | Rolling Bridge–DFM Ensemble | 45 |

## Robust adaptive selections

| forecast_stage | selected_component | forecasts |
|---|---|---|
| after_month_1 | Dynamic Factor Model | 45 |
| after_month_2 | Bridge–DFM Ensemble | 45 |
| early_quarter | Dynamic Factor Model | 45 |
| pre_advance_release | Bridge Ridge | 6 |
| pre_advance_release | Bridge–DFM Ensemble | 3 |
| pre_advance_release | Dynamic Factor Model | 36 |
| quarter_end | Bridge Ridge | 20 |
| quarter_end | Dynamic Factor Model | 3 |
| quarter_end | Rolling Bridge–DFM Ensemble | 22 |

## Robust selector stability

| forecast_stage | forecasts | switches | average_duration |
|---|---|---|---|
| early_quarter | 45 | 0 | 45.0 |
| after_month_1 | 45 | 0 | 45.0 |
| after_month_2 | 45 | 0 | 45.0 |
| quarter_end | 45 | 2 | 15.0 |
| pre_advance_release | 45 | 4 | 9.0 |

## Regime robustness

| forecast_stage | sample | observations | rmse | trimmed_rmse_10 | mae | p90_abs_error | max_abs_error | interval_coverage | average_interval_width |
|---|---|---|---|---|---|---|---|---|---|
| early_quarter | Full sample | 45 | 6.1835 | 1.5801 | 2.4964 | 4.136 | 34.3116 | 0.8444 | 5.9211 |
| early_quarter | Pre-pandemic (through 2019Q4) | 20 | 1.11 | 0.8046 | 0.847 | 1.8091 | 3.0852 | 0.95 | 4.0595 |
| early_quarter | Pandemic (2020Q1–2021Q2) | 6 | 16.4228 | 16.4228 | 11.3748 | 26.687 | 34.3116 | 0.3333 | 3.9424 |
| early_quarter | Post-pandemic (from 2021Q3) | 19 | 2.0222 | 1.7725 | 1.4288 | 3.5991 | 4.5981 | 0.8947 | 8.5056 |
| early_quarter | Last 20 quarters | 20 | 2.0539 | 1.5493 | 1.4865 | 3.4897 | 4.5981 | 0.9 | 8.4433 |
| after_month_1 | Full sample | 45 | 4.5461 | 1.8175 | 2.2786 | 4.7261 | 24.0144 | 0.8667 | 6.8201 |
| after_month_1 | Pre-pandemic (through 2019Q4) | 20 | 1.0914 | 0.8447 | 0.8388 | 2.1095 | 2.4675 | 0.95 | 4.1067 |
| after_month_1 | Pandemic (2020Q1–2021Q2) | 6 | 11.6087 | 11.6087 | 8.9453 | 17.8729 | 24.0144 | 0.3333 | 5.8162 |
| after_month_1 | Post-pandemic (from 2021Q3) | 19 | 2.2666 | 1.9671 | 1.6889 | 3.8043 | 5.2884 | 0.9474 | 9.9933 |
| after_month_1 | Last 20 quarters | 20 | 2.2707 | 1.7864 | 1.7217 | 3.7538 | 5.2884 | 0.95 | 10.0008 |
| after_month_2 | Full sample | 45 | 2.7593 | 1.8396 | 1.8585 | 5.3245 | 7.6539 | 0.8667 | 7.2677 |
| after_month_2 | Pre-pandemic (through 2019Q4) | 20 | 1.1507 | 1.0038 | 0.9891 | 1.7255 | 2.2221 | 0.95 | 3.9016 |
| after_month_2 | Pandemic (2020Q1–2021Q2) | 6 | 5.4756 | 5.4756 | 4.8144 | 7.4033 | 7.6031 | 0.3333 | 6.1919 |
| after_month_2 | Post-pandemic (from 2021Q3) | 19 | 2.6779 | 2.0772 | 1.8403 | 4.5808 | 7.6539 | 0.9474 | 11.1506 |
| after_month_2 | Last 20 quarters | 20 | 2.6359 | 1.7624 | 1.8306 | 4.5351 | 7.6539 | 0.95 | 11.1507 |
| quarter_end | Full sample | 45 | 2.6859 | 1.7092 | 1.809 | 4.7365 | 8.0669 | 0.8444 | 6.5239 |
| quarter_end | Pre-pandemic (through 2019Q4) | 20 | 1.0215 | 0.8659 | 0.8827 | 1.4689 | 2.1591 | 0.95 | 3.6855 |
| quarter_end | Pandemic (2020Q1–2021Q2) | 6 | 5.2915 | 5.2915 | 4.6577 | 7.7495 | 8.0669 | 0.3333 | 4.3964 |
| quarter_end | Post-pandemic (from 2021Q3) | 19 | 2.6732 | 2.1242 | 1.8845 | 4.3315 | 7.3861 | 0.8947 | 10.1836 |
| quarter_end | Last 20 quarters | 20 | 2.6298 | 1.7846 | 1.87 | 4.2302 | 7.3861 | 0.9 | 10.0022 |
| pre_advance_release | Full sample | 45 | 2.8613 | 1.7836 | 1.8622 | 5.01 | 8.7948 | 0.8667 | 7.4437 |
| pre_advance_release | Pre-pandemic (through 2019Q4) | 20 | 1.0556 | 0.876 | 0.8872 | 1.6699 | 2.1937 | 0.95 | 3.7994 |
| pre_advance_release | Pandemic (2020Q1–2021Q2) | 6 | 6.2986 | 6.2986 | 5.7126 | 8.3226 | 8.7948 | 0.3333 | 5.952 |
| pre_advance_release | Post-pandemic (from 2021Q3) | 19 | 2.3852 | 1.9163 | 1.6725 | 4.0902 | 6.4802 | 0.9474 | 11.7509 |
| pre_advance_release | Last 20 quarters | 20 | 2.355 | 1.6992 | 1.673 | 4.0868 | 6.4802 | 0.95 | 11.7239 |

## Model-owner decision

- [ ] Review every warning and record the decision.
- [ ] Confirm the stable stage-specific component map.
- [ ] Confirm that the robust adaptive policy remains shadow-only.
- [ ] Confirm the 80% interval method and revalidation triggers.
- [ ] Confirm that the live dashboard and news decomposition use the stable production forecast.
- [ ] Approve promotion to `US_GDP_NOWCAST_1A v1.0.0`.

Promotion is a manual governance action. This script never changes the model version automatically.
