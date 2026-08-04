# Model 1D v0.3.6 Fixed-Horizon Target Lock and Probabilistic Benchmark Audit

## Status

- Audit ID: `c99ac096-a9cb-4e39-b976-b0d4cfe018a1`
- Model: `US_MACRO_STATE_1D` v0.3.6 (`development`)
- Source stability ID: `4d97b730-7dcb-4ee6-9f89-bf5fff542a9d`
- Source candidate: `expanding_robust_z__policy__equal__sensitive__independent_normal`
- Source candidate v0.3.1 governance gate: `fail`
- Fixed-horizon governance result: `fail`
- Selection period: 2020-02-29 to 2024-07-31 (54 months)
- Consumed audit period: 2024-08-31 to 2026-03-31 (19 months)

This is research evidence only. It does not approve a Model 1D candidate and does not reopen the consumed audit for tuning.

## Target lock

| primary_target_mode   | primary_target_level   | secondary_target_level   | governance_reference   | latest_revised_substitution_allowed   |   complete_states |   expected_states |   missing_states |
|:----------------------|:-----------------------|:-------------------------|:-----------------------|:--------------------------------------|------------------:|------------------:|-----------------:|
| fixed_horizon_90d     | five_family            | eight_state_report_only  | soft_persistence       | False                                 |                70 |                73 |                3 |

The five-family fixed-90-day target is the locked primary research target. Latest-revised observations are not permitted as substitutes for missing fixed-horizon evidence. The eight-state subtype remains report-only.

## Fixed-horizon state availability

| state_date   |   expected_targets |   available_targets | complete_state   | state_available_date   | latest_actual_as_of_date   |
|:-------------|-------------------:|--------------------:|:-----------------|:-----------------------|:---------------------------|
| 2020-02-29   |                  8 |                   8 | True             | 2020-06-29             | 2020-06-15                 |
| 2020-03-31   |                  8 |                   8 | True             | 2020-06-29             | 2020-06-26                 |
| 2020-04-30   |                  8 |                   8 | True             | 2020-09-28             | 2020-09-15                 |
| 2020-05-31   |                  8 |                   8 | True             | 2020-09-28             | 2020-09-15                 |
| 2020-06-30   |                  8 |                   8 | True             | 2020-09-28             | 2020-09-15                 |
| 2020-07-31   |                  8 |                   8 | True             | 2020-12-29             | 2020-12-15                 |
| 2020-08-31   |                  8 |                   8 | True             | 2020-12-29             | 2020-12-15                 |
| 2020-09-30   |                  8 |                   8 | True             | 2020-12-29             | 2020-12-23                 |
| 2020-10-31   |                  8 |                   8 | True             | 2021-03-31             | 2021-03-31                 |
| 2020-11-30   |                  8 |                   8 | True             | 2021-03-31             | 2021-03-31                 |
| 2020-12-31   |                  8 |                   8 | True             | 2021-03-31             | 2021-03-31                 |
| 2021-01-31   |                  8 |                   8 | True             | 2021-06-29             | 2021-06-15                 |
| 2021-02-28   |                  8 |                   8 | True             | 2021-06-29             | 2021-06-15                 |
| 2021-03-31   |                  8 |                   8 | True             | 2021-06-29             | 2021-06-25                 |
| 2021-04-30   |                  8 |                   8 | True             | 2021-09-28             | 2021-09-15                 |
| 2021-05-31   |                  8 |                   8 | True             | 2021-09-28             | 2021-09-15                 |
| 2021-06-30   |                  8 |                   8 | True             | 2021-09-28             | 2021-09-15                 |
| 2021-07-31   |                  8 |                   8 | True             | 2021-12-29             | 2021-12-15                 |
| 2021-08-31   |                  8 |                   8 | True             | 2021-12-29             | 2021-12-15                 |
| 2021-09-30   |                  8 |                   8 | True             | 2021-12-29             | 2021-12-23                 |
| 2021-10-31   |                  8 |                   8 | True             | 2022-03-31             | 2022-03-31                 |
| 2021-11-30   |                  8 |                   8 | True             | 2022-03-31             | 2022-03-31                 |
| 2021-12-31   |                  8 |                   8 | True             | 2022-03-31             | 2022-03-31                 |
| 2022-01-31   |                  8 |                   8 | True             | 2022-06-29             | 2022-06-15                 |
| 2022-02-28   |                  8 |                   8 | True             | 2022-06-29             | 2022-06-15                 |
| 2022-03-31   |                  8 |                   8 | True             | 2022-06-29             | 2022-06-29                 |
| 2022-04-30   |                  8 |                   8 | True             | 2022-09-28             | 2022-09-15                 |
| 2022-05-31   |                  8 |                   8 | True             | 2022-09-28             | 2022-09-15                 |
| 2022-06-30   |                  8 |                   8 | True             | 2022-09-28             | 2022-09-15                 |
| 2022-07-31   |                  8 |                   8 | True             | 2022-12-29             | 2022-12-15                 |
| 2022-08-31   |                  8 |                   8 | True             | 2022-12-29             | 2022-12-15                 |
| 2022-09-30   |                  8 |                   8 | True             | 2022-12-29             | 2022-12-23                 |
| 2022-10-31   |                  8 |                   8 | True             | 2023-03-31             | 2023-03-31                 |
| 2022-11-30   |                  8 |                   8 | True             | 2023-03-31             | 2023-03-31                 |
| 2022-12-31   |                  8 |                   8 | True             | 2023-03-31             | 2023-03-31                 |
| 2023-01-31   |                  8 |                   8 | True             | 2023-06-29             | 2023-06-15                 |
| 2023-02-28   |                  8 |                   8 | True             | 2023-06-29             | 2023-06-15                 |
| 2023-03-31   |                  8 |                   8 | True             | 2023-06-29             | 2023-06-29                 |
| 2023-04-30   |                  8 |                   8 | True             | 2023-09-28             | 2023-09-15                 |
| 2023-05-31   |                  8 |                   8 | True             | 2023-09-28             | 2023-09-15                 |
| 2023-06-30   |                  8 |                   8 | True             | 2023-09-28             | 2023-09-28                 |
| 2023-07-31   |                  8 |                   8 | True             | 2023-12-29             | 2023-12-15                 |
| 2023-08-31   |                  8 |                   8 | True             | 2023-12-29             | 2023-12-15                 |
| 2023-09-30   |                  8 |                   8 | True             | 2023-12-29             | 2023-12-22                 |
| 2023-10-31   |                  8 |                   8 | True             | 2024-03-30             | 2024-03-15                 |
| 2023-11-30   |                  8 |                   8 | True             | 2024-03-30             | 2024-03-15                 |
| 2023-12-31   |                  8 |                   8 | True             | 2024-03-30             | 2024-03-29                 |
| 2024-01-31   |                  8 |                   8 | True             | 2024-06-29             | 2024-06-15                 |
| 2024-02-29   |                  8 |                   8 | True             | 2024-06-29             | 2024-06-15                 |
| 2024-03-31   |                  8 |                   8 | True             | 2024-06-29             | 2024-06-28                 |
| 2024-04-30   |                  8 |                   8 | True             | 2024-09-28             | 2024-09-15                 |
| 2024-05-31   |                  8 |                   8 | True             | 2024-09-28             | 2024-09-15                 |
| 2024-06-30   |                  8 |                   8 | True             | 2024-09-28             | 2024-09-27                 |
| 2024-07-31   |                  8 |                   8 | True             | 2024-12-29             | 2024-12-15                 |
| 2024-08-31   |                  8 |                   8 | True             | 2024-12-29             | 2024-12-15                 |
| 2024-09-30   |                  8 |                   8 | True             | 2024-12-29             | 2024-12-20                 |
| 2024-10-31   |                  8 |                   8 | True             | 2025-03-31             | 2025-03-31                 |
| 2024-11-30   |                  8 |                   8 | True             | 2025-03-31             | 2025-03-31                 |
| 2024-12-31   |                  8 |                   8 | True             | 2025-03-31             | 2025-03-31                 |
| 2025-01-31   |                  8 |                   8 | True             | 2025-06-29             | 2025-06-15                 |
| 2025-02-28   |                  8 |                   8 | True             | 2025-06-29             | 2025-06-15                 |
| 2025-03-31   |                  8 |                   8 | True             | 2025-06-29             | 2025-06-27                 |
| 2025-04-30   |                  8 |                   8 | True             | 2025-09-28             | 2025-09-15                 |
| 2025-05-31   |                  8 |                   8 | True             | 2025-09-28             | 2025-09-15                 |
| 2025-06-30   |                  8 |                   8 | True             | 2025-09-28             | 2025-09-26                 |
| 2025-07-31   |                  8 |                   8 | True             | 2025-12-29             | 2025-12-23                 |
| 2025-08-31   |                  8 |                   8 | True             | 2025-12-29             | 2025-12-23                 |
| 2025-09-30   |                  8 |                   8 | True             | 2025-12-29             | 2025-12-23                 |
| 2025-11-30   |                  8 |                   8 | True             | 2026-03-31             | 2026-03-31                 |
| 2025-12-31   |                  8 |                   8 | True             | 2026-03-31             | 2026-03-31                 |
| 2026-01-31   |                  8 |                   7 | False            |                        |                            |
| 2026-02-28   |                  8 |                   7 | False            |                        |                            |
| 2026-03-31   |                  8 |                   7 | False            |                        |                            |

## Missing fixed-horizon evidence

| state_date   | source_target   | target_period   | availability_status   | requested_evaluation_date   | actual_as_of_date   |   snapshot_gap_days |
|:-------------|:----------------|:----------------|:----------------------|:----------------------------|:--------------------|--------------------:|
| 2026-01-31   | GDPC1           | 2026Q1          | snapshot_too_stale    | 2026-06-29                  | 2026-04-30          |                  60 |
| 2026-02-28   | GDPC1           | 2026Q1          | snapshot_too_stale    | 2026-06-29                  | 2026-04-30          |                  60 |
| 2026-03-31   | GDPC1           | 2026Q1          | snapshot_too_stale    | 2026-06-29                  | 2026-04-30          |                  60 |

## Probabilistic benchmark design

The frozen source probabilities are compared with five causal benchmarks:

1. hard persistence;
2. prior soft-target persistence;
3. Dirichlet-smoothed persistence;
4. first-order Markov probabilities;
5. rolling empirical family frequencies.

Each benchmark uses only target states whose fixed-horizon evidence was available by the forecast month.

## Rolling benchmark summary

|   soft_brier_rank | benchmark_id          |   folds |   mean_family_accuracy |   mean_family_balanced_accuracy |   mean_family_macro_f1 |   mean_soft_brier |   mean_soft_log_loss |   mean_top2_coverage |   mean_confidence_weighted_accuracy |   mean_expected_calibration_error |   reference_win_rate |   mean_weighted_accuracy_margin |   mean_macro_f1_margin |   mean_soft_brier_improvement |
|------------------:|:----------------------|--------:|-----------------------:|--------------------------------:|-----------------------:|------------------:|---------------------:|---------------------:|------------------------------------:|----------------------------------:|---------------------:|--------------------------------:|-----------------------:|------------------------------:|
|                 1 | source                |       7 |               0.47619  |                        0.396825 |               0.262434 |          0.575949 |              1.55272 |             0.571429 |                            0.485741 |                          0.184198 |                    1 |                        0.264239 |               0.117445 |                      0.591796 |
|                 2 | rolling_frequency     |       7 |               0.380952 |                        0.325397 |               0.21182  |          0.599892 |              1.7545  |             0.595238 |                            0.379035 |                          0.259921 |                  nan |                      nan        |             nan        |                    nan        |
|                 3 | markov_first_order    |       7 |               0.238095 |                        0.25     |               0.162132 |          0.726927 |              1.91385 |             0.428571 |                            0.252336 |                          0.227026 |                  nan |                      nan        |             nan        |                    nan        |
|                 4 | dirichlet_persistence |       7 |               0.214286 |                        0.244048 |               0.144989 |          0.847179 |              2.03918 |             0.428571 |                            0.221501 |                          0.430864 |                  nan |                      nan        |             nan        |                    nan        |
|                 5 | soft_persistence      |       7 |               0.214286 |                        0.244048 |               0.144989 |          1.16774  |             17.5572  |             0.428571 |                            0.221501 |                          0.653439 |                  nan |                      nan        |             nan        |                    nan        |
|                 6 | hard_persistence      |       7 |               0.214286 |                        0.244048 |               0.144989 |          1.36959  |             21.5639  |             0.285714 |                            0.221501 |                          0.785714 |                  nan |                      nan        |             nan        |                    nan        |

The source records mean family macro-F1 0.262, mean soft Brier score 0.576, expected calibration error 0.184, and a fold win rate of 100.0% against the pre-specified soft-persistence reference.

## Brier decomposition diagnostics

| benchmark_id          |   mean_hard_brier |   mean_brier_reliability |   mean_brier_resolution |   mean_brier_uncertainty |
|:----------------------|------------------:|-------------------------:|------------------------:|-------------------------:|
| source                |          0.743618 |                 0.339667 |               0.172222  |                 0.571429 |
| rolling_frequency     |          0.771164 |                 0.230966 |               0.0365079 |                 0.571429 |
| markov_first_order    |          0.91963  |                 0.440823 |               0.0984127 |                 0.571429 |
| dirichlet_persistence |          1.0306   |                 0.538556 |               0.081746  |                 0.571429 |
| soft_persistence      |          1.34725  |                 0.852381 |               0.081746  |                 0.571429 |
| hard_persistence      |          1.57143  |                 1.05794  |               0.0579365 |                 0.571429 |

## Fold comparisons with the governance reference

| fold_id   | reference_benchmark   |   source_weighted_accuracy |   reference_weighted_accuracy |   weighted_accuracy_margin | source_beats_reference   |   source_macro_f1 |   reference_macro_f1 |   macro_f1_margin |   source_soft_brier |   reference_soft_brier |   soft_brier_improvement |   source_ece |   reference_ece |   source_brier_rank |
|:----------|:----------------------|---------------------------:|------------------------------:|---------------------------:|:-------------------------|------------------:|---------------------:|------------------:|--------------------:|-----------------------:|-------------------------:|-------------:|----------------:|--------------------:|
| fold_01   | soft_persistence      |                   0.385965 |                      0        |                   0.385965 | True                     |          0.142857 |             0        |         0.142857  |            0.463658 |               1.15318  |                 0.68952  |    0.24707   |        0.777778 |                   2 |
| fold_02   | soft_persistence      |                   0.333333 |                      0.191489 |                   0.141844 | True                     |          0.166667 |             0.08     |         0.0866667 |            0.705829 |               1.04618  |                 0.340353 |    0.215169  |        0.574074 |                   1 |
| fold_03   | soft_persistence      |                   0.506494 |                      0.331169 |                   0.175325 | True                     |          0.222222 |             0.166667 |         0.0555556 |            0.660139 |               1.15546  |                 0.495325 |    0.100098  |        0.537037 |                   1 |
| fold_04   | soft_persistence      |                   0.643411 |                      0.372093 |                   0.271318 | True                     |          0.296296 |             0.3      |        -0.0037037 |            0.460434 |               0.926383 |                 0.465949 |    0.250651  |        0.58642  |                   2 |
| fold_05   | soft_persistence      |                   0.656489 |                      0.343511 |                   0.312977 | True                     |          0.296296 |             0.190476 |         0.10582   |            0.481603 |               0.844079 |                 0.362475 |    0.220215  |        0.537037 |                   2 |
| fold_06   | soft_persistence      |                   0.519231 |                      0.134615 |                   0.384615 | True                     |          0.412698 |             0.111111 |         0.301587  |            0.628621 |               1.50114  |                 0.872522 |    0.0825195 |        0.746914 |                   1 |
| fold_07   | soft_persistence      |                   0.355263 |                      0.177632 |                   0.177632 | True                     |          0.3      |             0.166667 |         0.133333  |            0.631356 |               1.54778  |                 0.916426 |    0.173665  |        0.814815 |                   1 |

## Bootstrap margin versus soft persistence

- Mean confidence-weighted monthly margin: 0.2240
- Lower confidence bound: 0.1614
- Upper confidence bound: 0.3139

## Prospective shadow isolation

| prospective_shadow_start   |   available_shadow_months | first_shadow_month   | last_shadow_month   | selection_contains_shadow_month   | consumed_audit_contains_shadow_month   | prospective_isolation_pass   |
|:---------------------------|--------------------------:|:---------------------|:--------------------|:----------------------------------|:---------------------------------------|:-----------------------------|
| 2026-04-30                 |                         0 |                      |                     | False                             | False                                  | True                         |

## Governance checks

| check_id                               | passed   |   observed |   threshold | interpretation                                                                                    |
|:---------------------------------------|:---------|-----------:|------------:|:--------------------------------------------------------------------------------------------------|
| fixed_horizon_target_locked            | True     |   1        |        1    | The five-family fixed-90-day target is the locked primary research target.                        |
| fixed_horizon_state_completeness       | True     |   0.958904 |        0.95 | The locked target requires sufficient complete states without revised-value substitution.         |
| missing_evidence_documented            | True     |   1        |        1    | Every incomplete fixed-horizon state must have explicit missing-target evidence.                  |
| latest_revised_substitution_prohibited | True     |   1        |        1    | Missing fixed-horizon observations cannot be replaced with latest-revised values.                 |
| benchmark_availability_no_lookahead    | True     |   1        |        1    | Probabilistic benchmarks may only use target states available by the forecast month.              |
| source_reference_fold_win_rate         | True     |   1        |        0.6  | The source must beat the pre-specified soft-persistence reference in most folds.                  |
| bootstrap_margin_positive              | True     |   0.161376 |        0    | The block-bootstrap lower confidence bound versus the reference must be positive.                 |
| macro_f1_not_reduced                   | True     |   0.117445 |        0    | The source cannot improve common-family accuracy by reducing macro-F1.                            |
| soft_brier_improves_reference          | True     |   0.591796 |        0    | The source must improve soft Brier score over probabilistic persistence.                          |
| source_calibration_error               | True     |   0.184198 |        0.2  | Expected calibration error must remain below the research ceiling.                                |
| source_top2_coverage                   | False    |   0.571429 |        0.65 | The realised primary family should be contained in the top two source probabilities often enough. |
| prospective_shadow_isolation           | True     |   1        |        1    | Months beginning April 2026 remain outside selection and consumed audit.                          |

## Decision rule

Model 1D cannot return to candidate consideration unless the fixed-horizon target remains complete without revised-value substitution, benchmark construction is availability-consistent, the source wins at least five of seven folds against soft persistence, the bootstrap lower margin is positive, macro-F1 is not reduced, and probability calibration remains acceptable.
