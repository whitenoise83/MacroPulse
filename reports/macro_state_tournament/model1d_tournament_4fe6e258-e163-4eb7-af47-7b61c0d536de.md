# Model 1D v0.3 Tournament Report

- Tournament ID: `4fe6e258-e163-4eb7-af47-7b61c0d536de`
- Reconstruction ID: `9b9995cc-282b-4d21-a33c-e59661cc10bc`
- Model: `US_MACRO_STATE_1D` v`0.3.0`
- Status: research tournament; not production approved

## Chronological split

- Training: 2020-02-29 to 2023-01-31 (36 states)
- Validation: 2023-02-28 to 2024-07-31 (18 states)
- Holdout: 2024-08-31 to 2026-03-31 (19 states)

## Provisional winner

- Candidate: `expanding_robust_z__policy__hard_data__sensitive__independent_normal`
- Core specification: `expanding_robust_z__policy__hard_data__sensitive`
- Uncertainty method: `independent_normal`
- Validation score: 76.31
- Validation rank: 1
- Holdout score: 41.22
- Holdout rank: 34
- Holdout exact-regime accuracy beats best naive baseline: False

## Naive baselines

```json
{
  "training_mode_regime": "stagflation_risk",
  "validation_mode_accuracy": 0.05555555555555555,
  "validation_persistence_accuracy": 0.3888888888888889,
  "holdout_mode_accuracy": 0.10526315789473684,
  "holdout_persistence_accuracy": 0.6111111111111112
}
```

## Final leaderboard

| final_rank | candidate_id | core_candidate_id | uncertainty_id | final_score | holdout_final_rank | holdout_final_score | brier_score | log_loss | coverage_80 | top1_accuracy | holdout_brier_score | holdout_log_loss | holdout_coverage_80 | holdout_top1_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | expanding_robust_z__policy__hard_data__sensitive__independent_normal | expanding_robust_z__policy__hard_data__sensitive | independent_normal | 76.3054 | 34 | 41.2239 | 0.6878 | 1.4126 | 0.9444 | 0.5000 | 0.9206 | 2.0901 | 0.6842 | 0.1053 |
| 2 | expanding_robust_z__policy__policy__sensitive__independent_normal | expanding_robust_z__policy__policy__sensitive | independent_normal | 76.2188 | 28 | 49.3025 | 0.6974 | 1.4405 | 0.8889 | 0.5556 | 0.8977 | 2.0190 | 0.7368 | 0.1579 |
| 3 | expanding_robust_z__policy__policy__sensitive__expanding_residual_copula | expanding_robust_z__policy__policy__sensitive | expanding_residual_copula | 75.6563 | 31 | 44.4900 | 0.6932 | 1.4369 | 0.9444 | 0.6667 | 0.9109 | 2.0478 | 0.6842 | 0.1053 |
| 4 | expanding_robust_z__core_heavy__policy__sensitive__expanding_residual_copula | expanding_robust_z__core_heavy__policy__sensitive | expanding_residual_copula | 75.1716 | 25 | 51.8063 | 0.7117 | 1.4868 | 0.8333 | 0.5556 | 0.9030 | 2.0144 | 0.7895 | 0.1053 |
| 5 | expanding_robust_z__core_heavy__policy__sensitive__independent_normal | expanding_robust_z__core_heavy__policy__sensitive | independent_normal | 74.4008 | 29 | 48.9938 | 0.7125 | 1.4773 | 0.8333 | 0.5000 | 0.9149 | 2.0551 | 0.7368 | 0.1579 |
| 6 | expanding_robust_z__policy__equal__sensitive__expanding_residual_copula | expanding_robust_z__policy__equal__sensitive | expanding_residual_copula | 74.3091 | 23 | 55.6448 | 0.6925 | 1.4375 | 0.8889 | 0.6111 | 0.9282 | 2.0811 | 0.6842 | 0.0526 |
| 7 | expanding_robust_z__core_heavy__equal__sensitive__independent_normal | expanding_robust_z__core_heavy__equal__sensitive | independent_normal | 74.1961 | 6 | 64.0901 | 0.6992 | 1.4576 | 0.8889 | 0.5000 | 0.9147 | 2.0094 | 0.7368 | 0.1053 |
| 8 | expanding_robust_z__policy__equal__sensitive__independent_normal | expanding_robust_z__policy__equal__sensitive | independent_normal | 73.8924 | 15 | 59.0614 | 0.6934 | 1.4319 | 0.8889 | 0.5000 | 0.9210 | 2.0473 | 0.6842 | 0.0526 |
| 9 | expanding_robust_z__policy__policy__baseline__independent_normal | expanding_robust_z__policy__policy__baseline | independent_normal | 73.4873 | 5 | 64.1008 | 0.7600 | 1.4966 | 0.8333 | 0.3333 | 0.6483 | 1.2765 | 0.9474 | 0.4211 |
| 10 | expanding_robust_z__core_heavy__hard_data__sensitive__independent_normal | expanding_robust_z__core_heavy__hard_data__sensitive | independent_normal | 72.7998 | 33 | 43.8406 | 0.7119 | 1.4752 | 0.8889 | 0.5000 | 0.9152 | 2.0697 | 0.6316 | 0.1053 |
| 11 | expanding_robust_z__policy__hard_data__sensitive__expanding_residual_copula | expanding_robust_z__policy__hard_data__sensitive | expanding_residual_copula | 71.9096 | 36 | 36.7031 | 0.7010 | 1.4456 | 0.9444 | 0.5556 | 0.9252 | 2.1191 | 0.5789 | 0.1579 |
| 12 | expanding_robust_z__core_heavy__equal__baseline__fixed_gaussian_copula | expanding_robust_z__core_heavy__equal__baseline | fixed_gaussian_copula | 71.6721 | 7 | 64.0318 | 0.7437 | 1.5057 | 0.8889 | 0.4444 | 0.7037 | 1.4569 | 0.8947 | 0.4737 |

## Core leaderboard

| core_rank | candidate_id | core_score | holdout_core_rank | holdout_core_score | dimension_rmse | exact_regime_accuracy | family_accuracy | sign_accuracy | churn_gap | distribution_jsd | regime_collapse_penalty | holdout_dimension_rmse | holdout_exact_regime_accuracy | holdout_family_accuracy | holdout_sign_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | expanding_robust_z__core_heavy__policy__baseline | 82.2346 | 28 | 55.5926 | 0.7569 | 0.5000 | 0.5556 | 0.5741 | 0.0000 | 0.0964 | 0.0000 | 0.6264 | 0.3684 | 0.3684 | 0.4211 |
| 2 | expanding_robust_z__policy__policy__baseline | 80.1605 | 25 | 58.8642 | 0.7587 | 0.5000 | 0.5556 | 0.5741 | 0.0000 | 0.0964 | 0.0000 | 0.6254 | 0.3684 | 0.3684 | 0.4386 |
| 3 | expanding_robust_z__core_heavy__equal__baseline | 79.3827 | 18 | 65.9383 | 0.7596 | 0.5000 | 0.5556 | 0.5926 | 0.0000 | 0.0964 | 0.0000 | 0.6085 | 0.3684 | 0.3684 | 0.4211 |
| 4 | expanding_robust_z__core_heavy__policy__sensitive | 77.8642 | 30 | 53.0864 | 0.7569 | 0.5000 | 0.6667 | 0.5741 | 0.0000 | 0.1243 | 0.0318 | 0.6264 | 0.2632 | 0.4211 | 0.4211 |
| 5 | expanding_robust_z__core_heavy__hard_data__sensitive | 76.8272 | 34 | 52.1235 | 0.7572 | 0.5000 | 0.6667 | 0.5741 | 0.0000 | 0.1243 | 0.0318 | 0.6673 | 0.2632 | 0.4211 | 0.4386 |
| 6 | expanding_robust_z__policy__equal__baseline | 76.2716 | 29 | 53.7654 | 0.7614 | 0.5000 | 0.5556 | 0.5926 | 0.0000 | 0.0964 | 0.0000 | 0.6075 | 0.2632 | 0.2632 | 0.4386 |
| 7 | expanding_robust_z__policy__policy__sensitive | 76.0864 | 42 | 48.7654 | 0.7587 | 0.5556 | 0.6667 | 0.5741 | 0.0588 | 0.1161 | 0.0828 | 0.6254 | 0.2105 | 0.3684 | 0.4386 |
| 8 | expanding_robust_z__core_heavy__hard_data__baseline | 75.8025 | 22 | 60.6173 | 0.7572 | 0.4444 | 0.4444 | 0.5741 | 0.0588 | 0.1012 | 0.0000 | 0.6673 | 0.4211 | 0.4211 | 0.4386 |
| 9 | expanding_robust_z__policy__hard_data__sensitive | 75.0494 | 45 | 47.7901 | 0.7590 | 0.5556 | 0.6667 | 0.5741 | 0.0588 | 0.1161 | 0.0828 | 0.6664 | 0.2105 | 0.3684 | 0.4561 |
| 10 | expanding_robust_z__core_heavy__equal__sensitive | 75.0123 | 8 | 72.2716 | 0.7596 | 0.5000 | 0.6667 | 0.5926 | 0.0000 | 0.1243 | 0.0318 | 0.6085 | 0.4737 | 0.6316 | 0.4211 |
| 11 | expanding_robust_z__policy__hard_data__baseline | 73.7284 | 27 | 57.4198 | 0.7590 | 0.4444 | 0.4444 | 0.5741 | 0.0588 | 0.1012 | 0.0000 | 0.6664 | 0.3684 | 0.3684 | 0.4561 |
| 12 | expanding_robust_z__policy__equal__sensitive | 72.1975 | 6 | 73.1235 | 0.7614 | 0.5556 | 0.6667 | 0.5926 | 0.0588 | 0.1161 | 0.0828 | 0.6075 | 0.4211 | 0.5789 | 0.4386 |
| 13 | expanding_robust_z__policy__policy__conservative | 71.6049 | 11 | 71.8765 | 0.7587 | 0.4444 | 0.4444 | 0.5741 | 0.0000 | 0.0774 | 0.1852 | 0.6254 | 0.5263 | 0.5263 | 0.4386 |
| 14 | expanding_robust_z__policy__hard_data__conservative | 70.5679 | 19 | 64.8395 | 0.7590 | 0.4444 | 0.4444 | 0.5741 | 0.0000 | 0.0774 | 0.1852 | 0.6664 | 0.5263 | 0.5263 | 0.4561 |
| 15 | target_centered__core_heavy__hard_data__conservative | 68.5185 | 32 | 52.2346 | 0.9508 | 0.3889 | 0.4444 | 0.7037 | 0.1176 | 0.0894 | 0.0000 | 1.1843 | 0.3684 | 0.3684 | 0.4912 |

## Governance interpretation

The winner is provisional. It was selected on the validation window and audited
on a sealed chronological holdout. Model 1D must not be promoted from this
report alone. A later release should assess specification stability, economic
event sensitivity, and whether the selected uncertainty method is calibrated
across subperiods.
