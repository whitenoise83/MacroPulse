# Model 1D v0.3.2 Regime-Target and Temporal-Decision Diagnostics

- Diagnostic ID: `be505dfb-23dc-4739-8680-cb6fe9940741`
- Source stability run: `4d97b730-7dcb-4ee6-9f89-bf5fff542a9d`
- Source candidate: `expanding_robust_z__policy__equal__sensitive__independent_normal`
- Reconstruction ID: `9b9995cc-282b-4d21-a33c-e59661cc10bc`
- Model: `US_MACRO_STATE_1D` v`0.3.2`
- Status: research diagnostics only; not candidate or production approved

## Design

- Selection sample: 2020-02-29 to 2024-07-31 (54 complete states)
- Rolling folds: 7
- Consumed audit: 2024-08-31 to 2026-03-31 (19 complete states)
- Temporal policies: raw monthly, hysteresis thresholds, one-month confirmation, persistence-prior probability filter
- The consumed audit is reported separately and has zero selection weight.

## Source target decomposition — selection

| dimension                    |   months |       rmse |        mae |       bias |   correlation |   accuracy |
|:-----------------------------|---------:|-----------:|-----------:|-----------:|--------------:|-----------:|
| growth                       |       54 |   1.54627  |   1.03235  |   0.483102 |      0.355709 |   0.62963  |
| inflation                    |       54 |   0.697985 |   0.520871 |  -0.175454 |      0.780569 |   0.740741 |
| labour                       |       54 |   0.702338 |   0.521421 |  -0.265685 |      0.309937 |   0.574074 |
| eight_regime_point_decision  |       54 | nan        | nan        | nan        |    nan        |   0.37037  |
| regime_family_point_decision |       54 | nan        | nan        | nan        |    nan        |   0.592593 |
| probability_top1_decision    |       54 | nan        | nan        | nan        |    nan        |   0.296296 |

## Source target decomposition — consumed audit

| dimension                    |   months |       rmse |        mae |        bias |   correlation |   accuracy |
|:-----------------------------|---------:|-----------:|-----------:|------------:|--------------:|-----------:|
| growth                       |       19 |   0.762944 |   0.588285 |   0.0517973 |     -0.341968 |  0.263158  |
| inflation                    |       19 |   0.481344 |   0.355635 |   0.0188785 |      0.342675 |  0.684211  |
| labour                       |       19 |   0.541822 |   0.410597 |   0.31154   |     -0.212992 |  0.631579  |
| eight_regime_point_decision  |       19 | nan        | nan        | nan         |    nan        |  0.421053  |
| regime_family_point_decision |       19 | nan        | nan        | nan         |    nan        |  0.578947  |
| probability_top1_decision    |       19 | nan        | nan        | nan         |    nan        |  0.0526316 |

## Temporal policy stability leaderboard

|   stability_rank | policy_id              |   stability_score |   median_fold_rank |   baseline_dominance_rate |   mean_exact_regime_accuracy |   mean_family_accuracy |   mean_transition_f1 |   mean_false_transition_rate |   bootstrap_margin_lower |   audit_rank | governance_pass   |
|-----------------:|:-----------------------|------------------:|-------------------:|--------------------------:|-----------------------------:|-----------------------:|---------------------:|-----------------------------:|-------------------------:|-------------:|:------------------|
|                1 | raw_monthly            |            85     |                  1 |                         0 |                     0.452381 |               0.619048 |            0.448299  |                     0.507143 |               -0.166667  |            1 | False             |
|                2 | hysteresis_thresholds  |            67.5   |                  2 |                         0 |                     0.5      |               0.595238 |            0.0571429 |                     0.214286 |               -0.0952381 |            3 | False             |
|                3 | one_month_confirmation |            51.875 |                  3 |                         0 |                     0.333333 |               0.428571 |            0.128571  |                     0.571429 |               -0.261905  |            2 | False             |
|                4 | persistence_prior      |            45.625 |                  4 |                         0 |                     0        |               0        |            0         |                     0        |               -0.619048  |            4 | False             |

## Research temporal leader

- Policy: `raw_monthly`
- Stability score: 85.00
- Consumed-audit rank: 1
- Governance gate: fail

### Gate failures

- naive-baseline dominance rate is below the gate
- transition recall is below the gate
- false-transition rate exceeds the gate
- regime-collapse fold rate exceeds the gate
- block-bootstrap margin versus the strongest naive baseline is not strictly positive

## Selected policy by fold

| fold_id   | evaluation_start   | evaluation_end   |   policy_rank |   policy_score |   exact_regime_accuracy |   family_accuracy |   stable_month_accuracy |   transition_month_accuracy |   transition_precision |   transition_recall |   transition_f1 |   false_transition_rate |   strongest_baseline_accuracy |   baseline_margin |
|:----------|:-------------------|:-----------------|--------------:|---------------:|------------------------:|------------------:|------------------------:|----------------------------:|-----------------------:|--------------------:|----------------:|------------------------:|------------------------------:|------------------:|
| fold_01   | 2022-08-31         | 2023-01-31       |             1 |         88.125 |                0.333333 |          0.666667 |                0.333333 |                    0.333333 |                   0.2  |            0.5      |        0.285714 |                    0.8  |                      0.5      |         -0.166667 |
| fold_02   | 2022-11-30         | 2023-04-30       |             2 |         60.625 |                0        |          0.333333 |                0        |                    0        |                   0.25 |            0.333333 |        0.285714 |                    0.75 |                      0.5      |         -0.5      |
| fold_03   | 2023-02-28         | 2023-07-31       |             1 |         81.875 |                0.5      |          0.666667 |                0.666667 |                    0.333333 |                   1    |            0.5      |        0.666667 |                    0    |                      0.5      |          0        |
| fold_04   | 2023-05-31         | 2023-10-31       |             2 |         64.375 |                0.666667 |          0.833333 |                1        |                    0.333333 |                   0    |            0        |        0        |                    1    |                      0.833333 |         -0.166667 |
| fold_05   | 2023-08-31         | 2024-01-31       |             2 |         76.875 |                0.5      |          0.666667 |                1        |                    0        |                   0.5  |            0.333333 |        0.4      |                    0.5  |                      0.666667 |         -0.166667 |
| fold_06   | 2023-11-30         | 2024-04-30       |             1 |         86.25  |                0.5      |          0.5      |                0.5      |                    0.5      |                   0.5  |            0.5      |        0.5      |                    0.5  |                      0.666667 |         -0.166667 |
| fold_07   | 2024-02-29         | 2024-07-31       |             1 |         95.625 |                0.666667 |          0.666667 |                0.5      |                    1        |                   1    |            1        |        1        |                    0    |                      0.666667 |          0        |

## Selected policy per-regime metrics — selection

| regime                    |   support |   forecast_count |   precision |   recall |       f1 |
|:--------------------------|----------:|-----------------:|------------:|---------:|---------:|
| hard_landing_risk         |         3 |                2 |    1        | 0.666667 | 0.8      |
| stagflation_risk          |         6 |                0 |    0        | 0        | 0        |
| overheating               |         6 |                2 |    0.5      | 0.166667 | 0.25     |
| disinflationary_expansion |        17 |               20 |    0.55     | 0.647059 | 0.594595 |
| balanced_expansion        |         5 |                5 |    0.2      | 0.2      | 0.2      |
| reflation                 |         5 |               16 |    0.1875   | 0.6      | 0.285714 |
| demand_slowdown           |         8 |                2 |    0        | 0        | 0        |
| mixed_transition          |         4 |                7 |    0.285714 | 0.5      | 0.363636 |

## Selected policy transition events — selection

| event_type                 | actual_date   | actual_from_regime        | actual_to_regime          | predicted_date   | predicted_from_regime     | predicted_to_regime       | matched   |   lead_lag_months |
|:---------------------------|:--------------|:--------------------------|:--------------------------|:-----------------|:--------------------------|:--------------------------|:----------|------------------:|
| actual_transition          | 2020-04-30    | demand_slowdown           | hard_landing_risk         | 2020-05-31       | demand_slowdown           | hard_landing_risk         | True      |                 1 |
| actual_transition          | 2020-07-31    | hard_landing_risk         | reflation                 | 2020-07-31       | hard_landing_risk         | reflation                 | True      |                 0 |
| actual_transition          | 2020-08-31    | reflation                 | overheating               |                  |                           |                           | False     |               nan |
| actual_transition          | 2020-09-30    | overheating               | mixed_transition          | 2020-09-30       | reflation                 | mixed_transition          | True      |                 0 |
| actual_transition          | 2020-10-31    | mixed_transition          | disinflationary_expansion | 2020-11-30       | mixed_transition          | disinflationary_expansion | True      |                 1 |
| actual_transition          | 2020-12-31    | disinflationary_expansion | reflation                 | 2021-01-31       | disinflationary_expansion | reflation                 | True      |                 1 |
| actual_transition          | 2021-02-28    | reflation                 | disinflationary_expansion |                  |                           |                           | False     |               nan |
| actual_transition          | 2021-03-31    | disinflationary_expansion | reflation                 | 2021-03-31       | mixed_transition          | reflation                 | True      |                 0 |
| actual_transition          | 2021-04-30    | reflation                 | overheating               |                  |                           |                           | False     |               nan |
| actual_transition          | 2021-07-31    | overheating               | mixed_transition          |                  |                           |                           | False     |               nan |
| actual_transition          | 2021-08-31    | mixed_transition          | balanced_expansion        |                  |                           |                           | False     |               nan |
| actual_transition          | 2021-10-31    | balanced_expansion        | overheating               | 2021-11-30       | reflation                 | overheating               | True      |                 1 |
| actual_transition          | 2021-11-30    | overheating               | reflation                 | 2021-10-31       | disinflationary_expansion | reflation                 | True      |                -1 |
| actual_transition          | 2021-12-31    | reflation                 | overheating               |                  |                           |                           | False     |               nan |
| actual_transition          | 2022-01-31    | overheating               | stagflation_risk          |                  |                           |                           | False     |               nan |
| actual_transition          | 2022-04-30    | stagflation_risk          | demand_slowdown           |                  |                           |                           | False     |               nan |
| actual_transition          | 2022-05-31    | demand_slowdown           | stagflation_risk          |                  |                           |                           | False     |               nan |
| actual_transition          | 2022-07-31    | stagflation_risk          | disinflationary_expansion | 2022-08-31       | reflation                 | disinflationary_expansion | True      |                 1 |
| actual_transition          | 2022-08-31    | disinflationary_expansion | balanced_expansion        | 2022-09-30       | disinflationary_expansion | balanced_expansion        | True      |                 1 |
| actual_transition          | 2022-10-31    | balanced_expansion        | disinflationary_expansion | 2022-10-31       | balanced_expansion        | disinflationary_expansion | True      |                 0 |
| actual_transition          | 2023-01-31    | disinflationary_expansion | stagflation_risk          |                  |                           |                           | False     |               nan |
| actual_transition          | 2023-02-28    | stagflation_risk          | demand_slowdown           | 2022-12-31       | balanced_expansion        | demand_slowdown           | True      |                -2 |
| actual_transition          | 2023-04-30    | demand_slowdown           | balanced_expansion        |                  |                           |                           | False     |               nan |
| actual_transition          | 2023-05-31    | balanced_expansion        | disinflationary_expansion | 2023-04-30       | mixed_transition          | disinflationary_expansion | True      |                -1 |
| actual_transition          | 2023-09-30    | disinflationary_expansion | mixed_transition          |                  |                           |                           | False     |               nan |
| actual_transition          | 2023-10-31    | mixed_transition          | disinflationary_expansion | 2023-11-30       | balanced_expansion        | disinflationary_expansion | True      |                 1 |
| actual_transition          | 2024-01-31    | disinflationary_expansion | demand_slowdown           |                  |                           |                           | False     |               nan |
| actual_transition          | 2024-04-30    | demand_slowdown           | disinflationary_expansion | 2024-03-31       | balanced_expansion        | disinflationary_expansion | True      |                -1 |
| actual_transition          | 2024-07-31    | disinflationary_expansion | mixed_transition          | 2024-07-31       | disinflationary_expansion | mixed_transition          | True      |                 0 |
| false_predicted_transition |               |                           |                           | 2020-04-30       | disinflationary_expansion | demand_slowdown           | False     |               nan |
| false_predicted_transition |               |                           |                           | 2021-02-28       | reflation                 | mixed_transition          | False     |               nan |
| false_predicted_transition |               |                           |                           | 2021-09-30       | reflation                 | disinflationary_expansion | False     |               nan |
| false_predicted_transition |               |                           |                           | 2022-01-31       | overheating               | reflation                 | False     |               nan |
| false_predicted_transition |               |                           |                           | 2022-05-31       | reflation                 | mixed_transition          | False     |               nan |
| false_predicted_transition |               |                           |                           | 2022-06-30       | mixed_transition          | reflation                 | False     |               nan |
| false_predicted_transition |               |                           |                           | 2022-11-30       | disinflationary_expansion | balanced_expansion        | False     |               nan |
| false_predicted_transition |               |                           |                           | 2023-01-31       | demand_slowdown           | disinflationary_expansion | False     |               nan |
| false_predicted_transition |               |                           |                           | 2023-02-28       | disinflationary_expansion | mixed_transition          | False     |               nan |
| false_predicted_transition |               |                           |                           | 2023-09-30       | disinflationary_expansion | balanced_expansion        | False     |               nan |
| false_predicted_transition |               |                           |                           | 2024-02-29       | disinflationary_expansion | balanced_expansion        | False     |               nan |

## Interpretation

This release diagnoses whether Model 1D's failure to beat persistence originates
in the continuous dimensions, the eight-regime target, or the temporal decision
layer. It does not retune normalization, weights, thresholds, or uncertainty.
The v0.3.1 source candidate failed promotion gates; no v0.3.2 policy can be
promoted directly from this diagnostic exercise.
