# Model 1D v0.3.4 Target-Definition and Benchmark-Validity Audit

## Status

- Audit ID: `594bc2f1-143e-469d-a861-319eb55d0126`
- Model: `US_MACRO_STATE_1D` v0.3.4 (`development`)
- Source stability ID: `4d97b730-7dcb-4ee6-9f89-bf5fff542a9d`
- Source candidate: `expanding_robust_z__policy__equal__sensitive__independent_normal`
- Source candidate v0.3.1 governance gate: `fail`
- Target-validity audit: `fail`
- Selection period: 2020-02-29 to 2024-07-31 (54 months)
- Consumed audit period: 2024-08-31 to 2026-03-31 (19 months)

This is diagnostic research evidence only. It does not approve a Model 1D candidate or alter the consumed-audit status.

## Validity checks

| check_id                           | passed   |   observed |   threshold | interpretation                                                                                  |
|:-----------------------------------|:---------|-----------:|------------:|:------------------------------------------------------------------------------------------------|
| forecast_lineage_no_lookahead      | True     |   1        |        1    | Forecast inputs must respect historical information cutoffs.                                    |
| actual_revision_vintage_recorded   | False    |   0        |        1    | Evaluation actuals require an explicit real-time revision vintage for a real-time target claim. |
| regime_perturbation_robustness     | False    |   0.657534 |        0.7  | Eight-state labels should remain unchanged under ±0.10 score perturbations.                     |
| family_perturbation_robustness     | False    |   0.753425 |        0.8  | Family labels should remain unchanged under ±0.10 score perturbations.                          |
| threshold_consensus                | False    |   0.452055 |        0.75 | Realised labels should be stable across the pre-specified threshold sets.                       |
| minimum_regime_support             | True     |   5        |        5    | Every eight-state label should have enough observations for meaningful validation.              |
| maximum_regime_share               | True     |   0.273973 |        0.4  | No single regime should dominate the realised target.                                           |
| source_beats_naive_baseline        | False    |   0        |        0.6  | The source classifier should beat the strongest naive benchmark in most rolling folds.          |
| family_forward_separation          | True     |   0.127252 |        0.05 | Regime families should separate subsequent macro outcomes.                                      |
| eight_state_incremental_separation | True     |   0.09939  |        0.02 | Eight-state subtyping should add economic separation beyond the five-family target.             |

## Construction and vintage lineage

| source_target   |   rows |   states |   information_cutoff_after_state |   data_as_of_after_state |   max_observation_after_cutoff |   target_leakage_rows |   future_target_period_rows |   missing_actual_release_date_rows | actual_revision_vintage_recorded   | evaluation_target_mode   |
|:----------------|-------:|---------:|---------------------------------:|-------------------------:|-------------------------------:|----------------------:|----------------------------:|-----------------------------------:|:-----------------------------------|:-------------------------|
| CES0500000003   |     73 |       73 |                                0 |                        0 |                              0 |                     0 |                           0 |                                  0 | False                              | ex_post_backtest_actual  |
| CPIAUCSL        |     73 |       73 |                                0 |                        0 |                              0 |                     0 |                           0 |                                  0 | False                              | ex_post_backtest_actual  |
| CPILFESL        |     73 |       73 |                                0 |                        0 |                              0 |                     0 |                           0 |                                  0 | False                              | ex_post_backtest_actual  |
| GDPC1           |     73 |       73 |                                0 |                        0 |                              0 |                     0 |                          48 |                                  0 | False                              | ex_post_backtest_actual  |
| PAYEMS          |     73 |       73 |                                0 |                        0 |                              0 |                     0 |                           0 |                                  0 | False                              | ex_post_backtest_actual  |
| PCEPI           |     73 |       73 |                                0 |                        0 |                              0 |                     0 |                           0 |                                  0 | False                              | ex_post_backtest_actual  |
| PCEPILFE        |     73 |       73 |                                0 |                        0 |                              0 |                     0 |                           0 |                                  0 | False                              | ex_post_backtest_actual  |
| UNRATE          |     73 |       73 |                                0 |                        0 |                              0 |                     0 |                           0 |                                  0 | False                              | ex_post_backtest_actual  |

The forecast lineage can pass no-look-ahead checks while the realised target remains ex-post. The current backtest actuals do not carry an explicit revision-vintage timestamp, so this audit does not treat the realised eight-state label as a proven real-time target.

## Label stability summary

- Mean eight-state boundary distance (L-infinity): 0.261
- Median eight-state boundary distance (L-infinity): 0.175
- Mean family boundary distance (L-infinity): 0.362
- Threshold-consensus share: 45.2%

## Realised occupancy

| label                     |   count |     share |   median_run_months |   maximum_run_months |
|:--------------------------|--------:|----------:|--------------------:|---------------------:|
| hard_landing_risk         |       5 | 0.0684932 |                 2.5 |                    3 |
| stagflation_risk          |       6 | 0.0821918 |                 2   |                    3 |
| overheating               |       6 | 0.0821918 |                 1   |                    3 |
| disinflationary_expansion |      20 | 0.273973  |                 2   |                    4 |
| balanced_expansion        |      13 | 0.178082  |                 2   |                    4 |
| reflation                 |       5 | 0.0684932 |                 1   |                    2 |
| demand_slowdown           |      11 | 0.150685  |                 2   |                    3 |
| mixed_transition          |       7 | 0.0958904 |                 1   |                    2 |

## Rolling benchmark summary

| benchmark_id       |   folds |   mean_exact_regime_accuracy |   mean_balanced_accuracy |   mean_macro_f1 |   mean_family_accuracy |   mean_family_macro_f1 |   mean_transition_recall |   mean_false_transition_rate |   mean_baseline_margin |   baseline_win_rate |
|:-------------------|--------:|-----------------------------:|-------------------------:|----------------:|-----------------------:|-----------------------:|-------------------------:|-----------------------------:|-----------------------:|--------------------:|
| persistence        |       7 |                     0.547619 |                 0.417857 |        0.372449 |               0.642857 |               0.439085 |                 0.238095 |                     0.47619  |             -0.0714286 |                   0 |
| markov_first_order |       7 |                     0.452381 |                 0.350397 |        0.299206 |               0.571429 |               0.377804 |                 0.238095 |                     0.47619  |             -0.166667  |                   0 |
| rolling_mode       |       7 |                     0.47619  |                 0.369048 |        0.237072 |               0.52381  |               0.283227 |                 0        |                     0.119048 |             -0.142857  |                   0 |
| source_direct      |       7 |                     0.452381 |                 0.346825 |        0.231529 |               0.619048 |               0.343506 |                 0.547619 |                     0.428571 |             -0.166667  |                   0 |
| forecast_sign_rule |       7 |                     0.333333 |                 0.312698 |        0.221882 |               0.357143 |               0.231406 |                 0.547619 |                     0.738095 |             -0.285714  |                   0 |
| training_mode      |       7 |                     0.428571 |                 0.285714 |        0.214141 |               0.452381 |               0.239538 |                 0        |                     0        |             -0.190476  |                   0 |

The source direct classifier has mean exact accuracy 45.2%, mean macro-F1 0.232, and a rolling-fold win rate of 0.0% against the strongest naive benchmark.

## Consumed-audit benchmarks

|   audit_rank | benchmark_id       |   exact_regime_accuracy |   balanced_accuracy |   macro_f1 |   family_accuracy |   family_macro_f1 |   transition_recall |   false_transition_rate | strongest_naive_benchmark   |   baseline_margin |
|-------------:|:-------------------|------------------------:|--------------------:|-----------:|------------------:|------------------:|--------------------:|------------------------:|:----------------------------|------------------:|
|            1 | persistence        |                0.555556 |            0.591667 |  0.537143  |          0.611111 |          0.550794 |               0.375 |                0.5      | persistence                 |         0         |
|            2 | markov_first_order |                0.578947 |            0.558333 |  0.486667  |          0.684211 |          0.466667 |               0.375 |                0.444444 | persistence                 |         0.0233918 |
|            3 | source_direct      |                0.421053 |            0.241667 |  0.227368  |          0.578947 |          0.49697  |               0.75  |                0.333333 | persistence                 |        -0.134503  |
|            4 | forecast_sign_rule |                0.105263 |            0.133333 |  0.0693878 |          0.210526 |          0.12381  |               0.75  |                0.666667 | persistence                 |        -0.450292  |
|            5 | training_mode      |                0.157895 |            0.2      |  0.0545455 |          0.578947 |          0.244444 |               0     |                0        | persistence                 |        -0.397661  |
|            6 | rolling_mode       |                0.105263 |            0.05     |  0.04      |          0.473684 |          0.214286 |               0.25  |                0.111111 | persistence                 |        -0.450292  |

The consumed audit is reported for external evidence only and is not used to tune the target definition or select a benchmark.

## Economic separation

|   horizon_months | dimension   | target_level   | outcome_type   |   observations |   groups_observed |   minimum_group_support |   maximum_group_share |   eta_squared |
|-----------------:|:------------|:---------------|:---------------|---------------:|------------------:|------------------------:|----------------------:|--------------:|
|                1 | growth      | eight_state    | future_level   |             71 |                 8 |                       5 |              0.267606 |     0.486168  |
|                1 | growth      | eight_state    | forward_change |             71 |                 8 |                       5 |              0.267606 |     0.197557  |
|                1 | growth      | five_family    | future_level   |             71 |                 5 |                       6 |              0.43662  |     0.425881  |
|                1 | growth      | five_family    | forward_change |             71 |                 5 |                       6 |              0.43662  |     0.136862  |
|                1 | inflation   | eight_state    | future_level   |             71 |                 8 |                       5 |              0.267606 |     0.363833  |
|                1 | inflation   | eight_state    | forward_change |             71 |                 8 |                       5 |              0.267606 |     0.283554  |
|                1 | inflation   | five_family    | future_level   |             71 |                 5 |                       6 |              0.43662  |     0.301223  |
|                1 | inflation   | five_family    | forward_change |             71 |                 5 |                       6 |              0.43662  |     0.170384  |
|                1 | labour      | eight_state    | future_level   |             71 |                 8 |                       5 |              0.267606 |     0.221864  |
|                1 | labour      | eight_state    | forward_change |             71 |                 8 |                       5 |              0.267606 |     0.195651  |
|                1 | labour      | five_family    | future_level   |             71 |                 5 |                       6 |              0.43662  |     0.197318  |
|                1 | labour      | five_family    | forward_change |             71 |                 5 |                       6 |              0.43662  |     0.0377424 |
|                3 | growth      | eight_state    | future_level   |             67 |                 8 |                       5 |              0.283582 |     0.176647  |
|                3 | growth      | eight_state    | forward_change |             67 |                 8 |                       5 |              0.283582 |     0.504426  |
|                3 | growth      | five_family    | future_level   |             67 |                 5 |                       6 |              0.41791  |     0.0861515 |
|                3 | growth      | five_family    | forward_change |             67 |                 5 |                       6 |              0.41791  |     0.42078   |
|                3 | inflation   | eight_state    | future_level   |             67 |                 8 |                       5 |              0.283582 |     0.25995   |
|                3 | inflation   | eight_state    | forward_change |             67 |                 8 |                       5 |              0.283582 |     0.268368  |
|                3 | inflation   | five_family    | future_level   |             67 |                 5 |                       6 |              0.41791  |     0.110688  |
|                3 | inflation   | five_family    | forward_change |             67 |                 5 |                       6 |              0.41791  |     0.123599  |
|                3 | labour      | eight_state    | future_level   |             67 |                 8 |                       5 |              0.283582 |     0.24333   |
|                3 | labour      | eight_state    | forward_change |             67 |                 8 |                       5 |              0.283582 |     0.183744  |
|                3 | labour      | five_family    | future_level   |             67 |                 5 |                       6 |              0.41791  |     0.184917  |
|                3 | labour      | five_family    | forward_change |             67 |                 5 |                       6 |              0.41791  |     0.0410194 |
|                6 | growth      | eight_state    | future_level   |             62 |                 8 |                       3 |              0.274194 |     0.276197  |
|                6 | growth      | eight_state    | forward_change |             62 |                 8 |                       3 |              0.274194 |     0.70589   |
|                6 | growth      | five_family    | future_level   |             62 |                 5 |                       5 |              0.419355 |     0.188847  |
|                6 | growth      | five_family    | forward_change |             62 |                 5 |                       5 |              0.419355 |     0.679749  |
|                6 | inflation   | eight_state    | future_level   |             62 |                 8 |                       3 |              0.274194 |     0.26774   |
|                6 | inflation   | eight_state    | forward_change |             62 |                 8 |                       3 |              0.274194 |     0.283397  |
|                6 | inflation   | five_family    | future_level   |             62 |                 5 |                       5 |              0.419355 |     0.235715  |
|                6 | inflation   | five_family    | forward_change |             62 |                 5 |                       5 |              0.419355 |     0.20474   |
|                6 | labour      | eight_state    | future_level   |             62 |                 8 |                       3 |              0.274194 |     0.212208  |
|                6 | labour      | eight_state    | forward_change |             62 |                 8 |                       3 |              0.274194 |     0.297719  |
|                6 | labour      | five_family    | future_level   |             62 |                 5 |                       5 |              0.419355 |     0.168156  |
|                6 | labour      | five_family    | forward_change |             62 |                 5 |                       5 |              0.419355 |     0.0643171 |

## Decision

The eight-state target should not advance to another candidate tournament unless the failed validity checks are resolved. In particular, real-time target vintages, label robustness, minimum regime support, benchmark dominance, and incremental economic separation beyond the five-family target require explicit evidence.
