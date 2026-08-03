# Model 1D v0.3.1 Rolling-Origin Stability Report

- Stability tournament ID: `4d97b730-7dcb-4ee6-9f89-bf5fff542a9d`
- Reconstruction ID: `9b9995cc-282b-4d21-a33c-e59661cc10bc`
- Source v0.3 tournament ID: `4fe6e258-e163-4eb7-af47-7b61c0d536de`
- Model: `US_MACRO_STATE_1D` v`0.3.1`
- Status: research stability tournament; not candidate or production approved

## Design

- Selection sample: 2020-02-29 to 2024-07-31 (54 complete states)
- Rolling folds: 7
- Evaluation window: 6 states
- Audit sample: 2024-08-31 to 2026-03-31 (19 complete states)
- Audit status: consumed external audit; reported but not used for ranking

## Research stability leader

- Candidate: `expanding_robust_z__policy__equal__sensitive__independent_normal`
- Core: `expanding_robust_z__policy__equal__sensitive`
- Uncertainty: `independent_normal`
- Stability score: 84.58
- Median fold rank: 8.0
- Worst fold rank: 27
- Leading-third rate: 85.7%
- Baseline dominance rate: 0.0%
- Uncertainty-method win rate: 42.9%
- Bootstrap baseline margin: -0.167 [-0.262, -0.071]
- Audit rank: 3 of 36
- Governance gate: fail

## Gate failures

- naive-baseline dominance rate is below the gate
- regime-collapse fold rate exceeds the gate
- block-bootstrap baseline margin is not strictly positive

## Core stability leaderboard

| stability_rank | candidate_id | stability_score | median_fold_rank | worst_fold_rank | leading_third_rate | baseline_dominance_rate | rank_std | average_regret | regime_collapse_fold_rate | governance_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | expanding_robust_z__core_heavy__equal__sensitive | 89.3519 | 7.0000 | 25 | 1.0000 | 0.0000 | 6.8004 | 8.0882 | 0.8571 | False |
| 2 | expanding_robust_z__core_heavy__policy__sensitive | 87.9321 | 10.0000 | 26 | 1.0000 | 0.0000 | 8.0964 | 8.2628 | 0.8571 | False |
| 3 | expanding_robust_z__policy__equal__sensitive | 87.8086 | 9.0000 | 23 | 1.0000 | 0.0000 | 7.0189 | 8.5379 | 0.8571 | False |
| 4 | expanding_robust_z__core_heavy__hard_data__sensitive | 84.7222 | 15.0000 | 25 | 1.0000 | 0.0000 | 8.1541 | 8.8554 | 0.8571 | False |
| 5 | expanding_robust_z__core_heavy__policy__baseline | 84.3827 | 9.0000 | 48 | 0.8571 | 0.2857 | 14.7690 | 10.1905 | 0.8571 | False |
| 6 | expanding_robust_z__core_heavy__equal__baseline | 84.0123 | 8.0000 | 44 | 0.8571 | 0.2857 | 13.8122 | 10.0159 | 0.8571 | False |
| 7 | expanding_robust_z__equal__equal__sensitive | 83.6728 | 14.0000 | 22 | 1.0000 | 0.0000 | 5.5144 | 10.7196 | 0.8571 | False |
| 8 | expanding_robust_z__policy__policy__sensitive | 83.3025 | 9.0000 | 31 | 0.8571 | 0.0000 | 8.9397 | 8.7813 | 0.8571 | False |
| 9 | expanding_robust_z__policy__equal__baseline | 83.2716 | 19.0000 | 36 | 0.8571 | 0.2857 | 11.5193 | 10.7707 | 0.8571 | False |
| 10 | expanding_robust_z__equal__policy__sensitive | 82.2531 | 12.0000 | 27 | 1.0000 | 0.0000 | 8.3788 | 10.8942 | 0.8571 | False |
| 11 | expanding_robust_z__core_heavy__hard_data__baseline | 80.8025 | 10.0000 | 52 | 0.8571 | 0.2857 | 15.3197 | 13.5891 | 0.8571 | False |
| 12 | expanding_robust_z__policy__policy__baseline | 80.4012 | 13.0000 | 40 | 0.7143 | 0.2857 | 13.0868 | 11.0141 | 0.8571 | False |
| 13 | expanding_robust_z__policy__hard_data__sensitive | 80.1543 | 14.0000 | 37 | 0.8571 | 0.0000 | 10.3075 | 9.9665 | 0.8571 | False |
| 14 | expanding_robust_z__policy__equal__conservative | 76.6975 | 16.0000 | 34 | 0.8571 | 0.0000 | 8.7831 | 13.8501 | 0.8571 | False |
| 15 | expanding_robust_z__policy__hard_data__baseline | 75.6481 | 18.0000 | 43 | 0.7143 | 0.2857 | 14.2414 | 15.0053 | 0.8571 | False |

## Final stability leaderboard

| stability_rank | candidate_id | stability_score | median_fold_rank | worst_fold_rank | leading_third_rate | baseline_dominance_rate | uncertainty_method_win_rate | proper_score_dominance_rate | bootstrap_margin_lower | audit_final_rank | governance_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | expanding_robust_z__policy__equal__sensitive__independent_normal | 84.5833 | 8.0000 | 27 | 0.8571 | 0.0000 | 0.4286 | 1.0000 | -0.2619 | 3 | False |
| 2 | expanding_robust_z__core_heavy__equal__sensitive__independent_normal | 79.5139 | 12.0000 | 22 | 0.5714 | 0.0000 | 0.7143 | 1.0000 | -0.3095 | 1 | False |
| 3 | expanding_robust_z__policy__policy__sensitive__independent_normal | 76.8750 | 8.0000 | 29 | 0.7143 | 0.0000 | 0.4286 | 1.0000 | -0.2619 | 25 | False |
| 4 | expanding_robust_z__policy__equal__sensitive__expanding_residual_copula | 74.1667 | 12.0000 | 26 | 0.5714 | 0.0000 | 0.2857 | 0.2857 | -0.2619 | 6 | False |
| 5 | expanding_robust_z__policy__policy__sensitive__expanding_residual_copula | 70.4861 | 12.0000 | 27 | 0.5714 | 0.0000 | 0.4286 | 0.2857 | -0.2619 | 29 | False |
| 6 | expanding_robust_z__equal__equal__sensitive__expanding_residual_copula | 68.6111 | 4.0000 | 35 | 0.7143 | 0.0000 | 0.5714 | 0.7143 | -0.3095 | 14 | False |
| 7 | expanding_robust_z__core_heavy__policy__sensitive__independent_normal | 67.7083 | 12.0000 | 27 | 0.5714 | 0.0000 | 0.4286 | 1.0000 | -0.2857 | 31 | False |
| 8 | expanding_robust_z__core_heavy__equal__baseline__independent_normal | 63.3333 | 17.0000 | 30 | 0.2857 | 0.2857 | 0.5714 | 1.0000 | -0.2143 | 4 | False |
| 9 | expanding_robust_z__core_heavy__policy__sensitive__expanding_residual_copula | 62.7778 | 18.0000 | 27 | 0.2857 | 0.0000 | 0.2857 | 0.4286 | -0.2857 | 27 | False |
| 10 | expanding_robust_z__equal__policy__sensitive__independent_normal | 62.6389 | 9.0000 | 35 | 0.7143 | 0.0000 | 0.5714 | 1.0000 | -0.3095 | 35 | False |
| 11 | expanding_robust_z__core_heavy__hard_data__sensitive__independent_normal | 61.9444 | 14.0000 | 26 | 0.1429 | 0.0000 | 0.5714 | 1.0000 | -0.3095 | 33 | False |
| 12 | expanding_robust_z__equal__equal__sensitive__independent_normal | 61.8056 | 5.0000 | 33 | 0.5714 | 0.0000 | 0.2857 | 1.0000 | -0.3095 | 19 | False |
| 13 | expanding_robust_z__equal__policy__sensitive__expanding_residual_copula | 58.4722 | 10.0000 | 32 | 0.7143 | 0.0000 | 0.2857 | 0.2857 | -0.3095 | 36 | False |
| 14 | expanding_robust_z__core_heavy__equal__sensitive__expanding_residual_copula | 55.0000 | 16.0000 | 20 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.3095 | 9 | False |
| 15 | expanding_robust_z__policy__policy__sensitive__fixed_gaussian_copula | 53.5417 | 18.0000 | 29 | 0.4286 | 0.0000 | 0.1429 | 0.2857 | -0.2619 | 24 | False |

## Selected candidate by fold

| fold_id | evaluation_start | evaluation_end | final_rank | final_score | exact_regime_accuracy | strongest_baseline | strongest_baseline_accuracy | baseline_margin | brier_score | log_loss | coverage_80 | uncertainty_method_rank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fold_01 | 2022-08-31 | 2023-01-31 | 7 | 72.8792 | 0.3333 | persistence | 0.5000 | -0.1667 | 0.9557 | 2.8617 | 0.6667 | 2 |
| fold_02 | 2022-11-30 | 2023-04-30 | 5 | 64.4940 | 0.0000 | persistence | 0.5000 | -0.5000 | 1.0278 | 2.9750 | 0.5000 | 1 |
| fold_03 | 2023-02-28 | 2023-07-31 | 6 | 73.9313 | 0.5000 | training_mode | 0.5000 | 0.0000 | 0.7954 | 1.7394 | 0.6667 | 3 |
| fold_04 | 2023-05-31 | 2023-10-31 | 8 | 70.7060 | 0.6667 | training_mode | 0.8333 | -0.1667 | 0.6388 | 1.2933 | 1.0000 | 2 |
| fold_05 | 2023-08-31 | 2024-01-31 | 27 | 60.2901 | 0.5000 | training_mode | 0.6667 | -0.1667 | 0.6354 | 1.2606 | 1.0000 | 2 |
| fold_06 | 2023-11-30 | 2024-04-30 | 8 | 67.3929 | 0.5000 | persistence | 0.6667 | -0.1667 | 0.6280 | 1.2506 | 1.0000 | 1 |
| fold_07 | 2024-02-29 | 2024-07-31 | 9 | 72.1164 | 0.6667 | persistence | 0.6667 | 0.0000 | 0.6494 | 1.2956 | 1.0000 | 1 |

## Consumed audit leaderboard

| audit_final_rank | candidate_id | audit_final_score | audit_exact_regime_accuracy | audit_baseline_accuracy | audit_baseline_margin | audit_brier_score | audit_log_loss | audit_coverage_80 | audit_top1_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | expanding_robust_z__core_heavy__equal__sensitive__independent_normal | 67.2458 | 0.4737 | 0.5556 | -0.0819 | 0.9147 | 2.0094 | 0.7368 | 0.1053 |
| 2 | expanding_robust_z__core_heavy__equal__baseline__expanding_residual_copula | 66.2958 | 0.3684 | 0.5000 | -0.1316 | 0.6629 | 1.3570 | 0.8947 | 0.4737 |
| 3 | expanding_robust_z__policy__equal__sensitive__independent_normal | 65.9500 | 0.4211 | 0.5556 | -0.1345 | 0.9210 | 2.0473 | 0.6842 | 0.0526 |
| 4 | expanding_robust_z__core_heavy__equal__baseline__independent_normal | 64.7542 | 0.3684 | 0.5000 | -0.1316 | 0.6707 | 1.3591 | 0.8947 | 0.3684 |
| 5 | expanding_robust_z__policy__equal__sensitive__fixed_gaussian_copula | 64.5750 | 0.4211 | 0.5556 | -0.1345 | 0.9277 | 2.0770 | 0.7368 | 0.0526 |
| 6 | expanding_robust_z__policy__equal__sensitive__expanding_residual_copula | 62.7833 | 0.4211 | 0.5556 | -0.1345 | 0.9282 | 2.0811 | 0.6842 | 0.0526 |
| 7 | expanding_robust_z__core_heavy__equal__sensitive__fixed_gaussian_copula | 62.4750 | 0.4737 | 0.5556 | -0.0819 | 0.9212 | 2.0432 | 0.7368 | 0.0526 |
| 8 | expanding_robust_z__core_heavy__equal__baseline__fixed_gaussian_copula | 61.7125 | 0.3684 | 0.5000 | -0.1316 | 0.7037 | 1.4569 | 0.8947 | 0.4737 |
| 9 | expanding_robust_z__core_heavy__equal__sensitive__expanding_residual_copula | 61.5375 | 0.4737 | 0.5556 | -0.0819 | 0.9194 | 2.0246 | 0.6316 | 0.1053 |
| 10 | expanding_robust_z__policy__equal__baseline__expanding_residual_copula | 61.0292 | 0.2632 | 0.5000 | -0.2368 | 0.6884 | 1.3833 | 0.8947 | 0.3158 |
| 11 | expanding_robust_z__core_heavy__hard_data__baseline__expanding_residual_copula | 60.6000 | 0.4211 | 0.6111 | -0.1901 | 0.6062 | 1.2178 | 0.9474 | 0.5789 |
| 12 | expanding_robust_z__policy__equal__baseline__independent_normal | 60.1125 | 0.2632 | 0.5000 | -0.2368 | 0.6947 | 1.4084 | 0.8947 | 0.3684 |
| 13 | expanding_robust_z__core_heavy__hard_data__baseline__independent_normal | 59.8292 | 0.4211 | 0.6111 | -0.1901 | 0.6136 | 1.2184 | 0.9474 | 0.5263 |
| 14 | expanding_robust_z__equal__equal__sensitive__expanding_residual_copula | 57.9792 | 0.3158 | 0.5556 | -0.2398 | 0.9161 | 2.0782 | 0.6842 | 0.1053 |
| 15 | expanding_robust_z__policy__equal__baseline__fixed_gaussian_copula | 57.8625 | 0.2632 | 0.5000 | -0.2368 | 0.7405 | 1.5373 | 0.8947 | 0.3684 |

## Selected candidate by macro subperiod

| subperiod_id | start_date | end_date | months | dimension_rmse | exact_regime_accuracy | family_accuracy | brier_score | log_loss | coverage_80 | top1_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pandemic_reopening | 2020-02-29 | 2021-12-31 | 23 | 0.9191 | 0.3478 | 0.6957 | 0.8427 | 2.7701 | 0.6957 | 0.2609 |
| inflation_acceleration | 2022-01-31 | 2023-06-30 | 18 | 1.3889 | 0.2222 | 0.3889 | 1.0326 | 3.2109 | 0.3889 | 0.1111 |
| disinflation_late_cycle | 2023-07-31 | 2024-12-31 | 18 | 0.6211 | 0.6111 | 0.6667 | 0.7520 | 1.6046 | 0.7778 | 0.4444 |
| recent_reflation_risk | 2025-01-31 | 2026-03-31 | 14 | 0.6869 | 0.3571 | 0.5714 | 0.8717 | 1.8841 | 0.8571 | 0.0714 |

## Governance interpretation

The rolling-origin ranking replaces the unstable single validation split from
v0.3.0. The audit period has already been observed and is not used to select
the research leader. Passing this research tournament does not itself approve
a Model 1D candidate. Failure of any gate blocks candidate promotion.
