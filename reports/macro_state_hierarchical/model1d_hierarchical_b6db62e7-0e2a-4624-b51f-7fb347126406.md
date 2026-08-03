# Model 1D v0.3.3 Causal Calibration and Hierarchical Regime Diagnostics

- Diagnostic ID: `b6db62e7-0e2a-4624-b51f-7fb347126406`
- Source stability run: `4d97b730-7dcb-4ee6-9f89-bf5fff542a9d`
- Source candidate: `expanding_robust_z__policy__equal__sensitive__independent_normal`
- Reconstruction ID: `9b9995cc-282b-4d21-a33c-e59661cc10bc`
- Model: `US_MACRO_STATE_1D` v`0.3.3`
- Status: research diagnostics only; not candidate or production approved

## Design

- Selection sample: 2020-02-29 to 2024-07-31 (54 complete states)
- Rolling folds: 7
- Consumed audit: 2024-08-31 to 2026-03-31 (19 complete states)
- Calibration candidates: none, expanding bias correction, expanding affine shrinkage
- Decision architectures: direct eight-state, family-first, family-first with interval abstention
- The source normalization, weights, sensitive thresholds, and independent-normal uncertainty are fixed from v0.3.1.
- The consumed audit is reported separately and has zero selection weight.

## Stability leaderboard

|   stability_rank | candidate_id                                              |   stability_score |   median_fold_rank |   worst_fold_rank |   leading_third_rate |   baseline_dominance_rate |   mean_macro_f1 |   mean_balanced_accuracy |   mean_family_macro_f1 |   mean_transition_recall |   mean_false_transition_rate |   mean_abstention_rate |   bootstrap_margin_lower |   audit_rank | governance_pass   |
|-----------------:|:----------------------------------------------------------|------------------:|-------------------:|------------------:|---------------------:|--------------------------:|----------------:|-------------------------:|-----------------------:|-------------------------:|-----------------------------:|-----------------------:|-------------------------:|-------------:|:------------------|
|                1 | none__direct_eight_state                                  |           89.9444 |                  1 |                 3 |             1        |                         0 |       0.321712  |                0.346825  |               0.3943   |                 0.452381 |                     0.507143 |                      0 |                -0.263158 |            1 | False             |
|                2 | none__family_first                                        |           84.1667 |                  2 |                 4 |             0.857143 |                         0 |       0.329649  |                0.346825  |               0.35235  |                 0.5      |                     0.471429 |                      0 |                -0.263158 |            8 | False             |
|                3 | expanding_bias__direct_eight_state                        |           65.5    |                  5 |                 9 |             0.142857 |                         0 |       0.0802721 |                0.130952  |               0.355423 |                 0.119048 |                     0.714286 |                      0 |                -0.684211 |            3 | False             |
|                4 | expanding_affine_shrinkage__direct_eight_state            |           56      |                  6 |                 8 |             0.428571 |                         0 |       0.0699546 |                0.130952  |               0.325661 |                 0.047619 |                     0.785714 |                      0 |                -0.684211 |            2 | False             |
|                5 | expanding_affine_shrinkage__family_first                  |           53.3333 |                  5 |                 9 |             0.142857 |                         0 |       0.0960317 |                0.0714286 |               0.22585  |                 0.190476 |                     0.702381 |                      0 |                -0.684211 |            9 | False             |
|                6 | expanding_affine_shrinkage__family_first_interval_abstain |           43.1111 |                  6 |                 8 |             0        |                         0 |       0.047619  |                0.166667  |               0.047619 |                 0        |                     0        |                      1 |                -0.684211 |            6 | False             |
|                7 | none__family_first_interval_abstain                       |           41.4444 |                  6 |                 9 |             0.428571 |                         0 |       0.047619  |                0.166667  |               0.047619 |                 0        |                     0        |                      1 |                -0.684211 |            5 | False             |
|                8 | expanding_bias__family_first                              |           36.7222 |                  7 |                 9 |             0        |                         0 |       0.0651927 |                0.0952381 |               0.150227 |                 0.119048 |                     0.452381 |                      0 |                -0.684211 |            4 | False             |
|                9 | expanding_bias__family_first_interval_abstain             |           29.7778 |                  8 |                 9 |             0        |                         0 |       0.047619  |                0.166667  |               0.047619 |                 0        |                     0        |                      1 |                -0.684211 |            7 | False             |

## Research leader

- Candidate: `none__direct_eight_state`
- Calibration: `none`
- Architecture: `direct_eight_state`
- Stability score: 89.94
- Consumed-audit rank: 1
- Governance gate: fail

### Gate failures

- naive-baseline dominance rate is below the gate
- eight-regime balanced accuracy is below the gate
- regime-family macro-F1 is below the gate
- transition recall is below the gate
- false-transition rate exceeds the gate
- regime-collapse fold rate exceeds the gate
- block-bootstrap margin versus the strongest naive baseline is not strictly positive

## Research leader by fold

| fold_id   | evaluation_start   | evaluation_end   |   fold_rank |   fold_score |   dimension_rmse |   growth_bias |   inflation_bias |   labour_bias |   exact_regime_accuracy |   balanced_accuracy |   macro_f1 |   family_accuracy |   family_balanced_accuracy |   family_macro_f1 |   transition_recall |   false_transition_rate |   baseline_margin |   abstention_rate | regime_collapse   |
|:----------|:-------------------|:-----------------|------------:|-------------:|-----------------:|--------------:|-----------------:|--------------:|------------------------:|--------------------:|-----------:|------------------:|---------------------------:|------------------:|--------------------:|------------------------:|------------------:|------------------:|:------------------|
| fold_01   | 2022-08-31         | 2023-01-31       |           1 |      92.0556 |         0.762992 |    -0.119595  |       -0.334264  |    -0.197854  |                0.333333 |            0.277778 |   0.277778 |          0.666667 |                   0.4      |          0.4      |            0.5      |                    0.8  |         -0.166667 |                 0 | False             |
| fold_02   | 2022-11-30         | 2023-04-30       |           3 |      55.6667 |         1.04816  |     0.703665  |       -0.102396  |    -0.25237   |                0        |            0        |   0        |          0.333333 |                   0.222222 |          0.222222 |            0.333333 |                    0.75 |         -0.5      |                 0 | False             |
| fold_03   | 2023-02-28         | 2023-07-31       |           1 |      88.3333 |         0.897945 |     0.543102  |        0.015416  |    -0.0661523 |                0.5      |            0.333333 |   0.285714 |          0.666667 |                   0.5      |          0.5      |            0.5      |                    0    |          0        |                 0 | True              |
| fold_04   | 2023-05-31         | 2023-10-31       |           1 |      75.8333 |         0.83438  |    -0.924948  |        0.108887  |     0.318605  |                0.666667 |            0.4      |   0.444444 |          0.833333 |                   0.5      |          0.454545 |            0        |                    1    |         -0.166667 |                 0 | True              |
| fold_05   | 2023-08-31         | 2024-01-31       |           1 |      77.5    |         0.838721 |    -0.773411  |       -0.01549   |     0.244978  |                0.5      |            0.25     |   0.25     |          0.666667 |                   0.333333 |          0.266667 |            0.333333 |                    0.5  |         -0.166667 |                 0 | True              |
| fold_06   | 2023-11-30         | 2024-04-30       |           2 |      79.1111 |         0.58301  |     0.22601   |       -0.0961083 |     0.110407  |                0.5      |            0.5      |   0.375    |          0.5      |                   0.5      |          0.333333 |            0.5      |                    0.5  |         -0.166667 |                 0 | True              |
| fold_07   | 2024-02-29         | 2024-07-31       |           1 |      93.3333 |         0.479106 |     0.0917025 |        0.122911  |     0.33682   |                0.666667 |            0.666667 |   0.619048 |          0.666667 |                   0.666667 |          0.583333 |            1        |                    0    |          0        |                 0 | False             |

## Calibration diagnostics

| dimension   |   mean_pre_bias |   mean_post_bias |   mean_alpha |   mean_beta |
|:------------|----------------:|-----------------:|-------------:|------------:|
| growth      |        0.732299 |         0.732299 |            0 |           1 |
| inflation   |       -0.257256 |        -0.257256 |            0 |           1 |
| labour      |       -0.43846  |        -0.43846  |            0 |           1 |

## Per-regime performance — causally expanding selection path

| regime                    |   support |   forecast_count |   precision |   recall |       f1 |
|:--------------------------|----------:|-----------------:|------------:|---------:|---------:|
| hard_landing_risk         |         0 |                0 |       0     | 0        | 0        |
| stagflation_risk          |         6 |                0 |       0     | 0        | 0        |
| overheating               |         2 |                2 |       0.5   | 0.5      | 0.5      |
| disinflationary_expansion |        14 |               16 |       0.625 | 0.714286 | 0.666667 |
| balanced_expansion        |         5 |                5 |       0.2   | 0.2      | 0.2      |
| reflation                 |         1 |                8 |       0     | 0        | 0        |
| demand_slowdown           |         6 |                1 |       0     | 0        | 0        |
| mixed_transition          |         2 |                4 |       0.25  | 0.5      | 0.333333 |

## Transition events — causally expanding selection path

| event_type                 | actual_date   | actual_from_regime        | actual_to_regime          | predicted_date   | predicted_from_regime     | predicted_to_regime       | matched   |   lead_lag_months |
|:---------------------------|:--------------|:--------------------------|:--------------------------|:-----------------|:--------------------------|:--------------------------|:----------|------------------:|
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
| false_predicted_transition |               |                           |                           | 2021-09-30       | reflation                 | disinflationary_expansion | False     |               nan |
| false_predicted_transition |               |                           |                           | 2022-01-31       | overheating               | reflation                 | False     |               nan |
| false_predicted_transition |               |                           |                           | 2022-05-31       | reflation                 | mixed_transition          | False     |               nan |
| false_predicted_transition |               |                           |                           | 2022-06-30       | mixed_transition          | reflation                 | False     |               nan |
| false_predicted_transition |               |                           |                           | 2022-11-30       | disinflationary_expansion | balanced_expansion        | False     |               nan |
| false_predicted_transition |               |                           |                           | 2023-01-31       | demand_slowdown           | disinflationary_expansion | False     |               nan |
| false_predicted_transition |               |                           |                           | 2023-02-28       | disinflationary_expansion | mixed_transition          | False     |               nan |
| false_predicted_transition |               |                           |                           | 2023-09-30       | disinflationary_expansion | balanced_expansion        | False     |               nan |
| false_predicted_transition |               |                           |                           | 2024-02-29       | disinflationary_expansion | balanced_expansion        | False     |               nan |

## Interpretation rules

This release is intentionally a small, pre-specified diagnostic rather than a
new broad tournament. A hierarchical or calibrated variant can advance only if
it improves balanced regime metrics, retains transition recall, avoids regime
collapse, beats the strongest naive baseline in most folds, and has a strictly
positive block-bootstrap lower margin. The consumed audit cannot be used to
retune or replace the selection leader.
