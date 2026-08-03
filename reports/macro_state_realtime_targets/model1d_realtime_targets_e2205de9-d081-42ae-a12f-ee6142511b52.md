# Model 1D v0.3.5 Real-Time Target Reconstruction and Soft-Label Audit

## Status

- Audit ID: `e2205de9-d081-42ae-a12f-ee6142511b52`
- Model: `US_MACRO_STATE_1D` v0.3.5 (`development`)
- Source stability ID: `4d97b730-7dcb-4ee6-9f89-bf5fff542a9d`
- Source candidate: `expanding_robust_z__policy__equal__sensitive__independent_normal`
- Source candidate v0.3.1 governance gate: `fail`
- Soft-target governance result: `fail`
- Selection period: 2020-02-29 to 2024-07-31 (54 months)
- Consumed audit period: 2024-08-31 to 2026-03-31 (19 months)

This is research evidence only. It does not approve a Model 1D candidate or release the consumed audit for tuning.

## Actual-vintage reconstruction completeness

| target_mode       |   expected_target_rows |   available_target_rows |   target_row_completeness |   expected_states |   complete_states |   complete_state_share |
|:------------------|-----------------------:|------------------------:|--------------------------:|------------------:|------------------:|-----------------------:|
| initial_release   |                    584 |                     584 |                  1        |                73 |                73 |               1        |
| fixed_horizon_90d |                    584 |                     581 |                  0.994863 |                73 |                70 |               0.958904 |
| latest_revised    |                    584 |                     584 |                  1        |                73 |                73 |               1        |

`initial_release` uses the actual outcomes recorded by the approved source pseudo-real-time backtests. `fixed_horizon_90d` uses the latest cached historical snapshot no later than target-period end plus 90 days. `latest_revised` uses the locally stored latest observation vintage. The audit makes no network request.

## Cross-vintage target agreement

| left_mode         | right_mode        |   common_months |   hard_family_agreement |   hard_regime_agreement |   soft_primary_family_agreement |   growth_score_mae |   inflation_score_mae |   labour_score_mae |
|:------------------|:------------------|----------------:|------------------------:|------------------------:|--------------------------------:|-------------------:|----------------------:|-------------------:|
| initial_release   | fixed_horizon_90d |              70 |                0.828571 |                0.728571 |                        0.828571 |           0.100806 |              0.112038 |           0.186113 |
| initial_release   | latest_revised    |              73 |                0.780822 |                0.69863  |                        0.712329 |           0.325946 |              0.187259 |           0.220779 |
| fixed_horizon_90d | latest_revised    |              70 |                0.742857 |                0.685714 |                        0.742857 |           0.298817 |              0.192803 |           0.115245 |

## Soft-label design

The five-family state is the primary target. The eight-state regime is retained as a secondary subtype. Each actual month is evaluated under the pre-specified threshold set and a deterministic ±0.10 score perturbation grid. The resulting family frequencies form the soft target distribution. A month is marked ambiguous when the top family probability or the probability margin is below the governance floor.

## Rolling benchmark summary

| target_mode       | benchmark_id   |   folds |   mean_family_accuracy |   mean_family_balanced_accuracy |   mean_family_macro_f1 |   mean_soft_brier |   mean_soft_log_loss |   mean_top2_coverage |   mean_confidence_weighted_accuracy |   baseline_win_rate |   mean_baseline_margin |
|:------------------|:---------------|--------:|-----------------------:|--------------------------------:|-----------------------:|------------------:|---------------------:|---------------------:|------------------------------------:|--------------------:|-----------------------:|
| fixed_horizon_90d | persistence    |       7 |               0.428571 |                        0.35119  |               0.334354 |          0.795545 |             10.6557  |             0.642857 |                            0.439998 |          nan        |            nan         |
| fixed_horizon_90d | source         |       7 |               0.47619  |                        0.396825 |               0.262434 |          0.575949 |              1.55272 |             0.571429 |                            0.485741 |            0.571429 |              0.0457424 |
| initial_release   | persistence    |       7 |               0.52381  |                        0.410317 |               0.366213 |          0.501012 |              7.23638 |             0.714286 |                            0.557922 |          nan        |            nan         |
| initial_release   | source         |       7 |               0.52381  |                        0.388889 |               0.285809 |          0.462704 |              1.51768 |             0.666667 |                            0.533554 |            0.285714 |             -0.0243681 |
| latest_revised    | persistence    |       7 |               0.5      |                        0.39246  |               0.377419 |          0.414578 |              6.8374  |             0.690476 |                            0.523691 |          nan        |            nan         |
| latest_revised    | source         |       7 |               0.547619 |                        0.400794 |               0.296946 |          0.387319 |              1.43523 |             0.619048 |                            0.547305 |            0.428571 |              0.0236141 |

For the initial-release target, the source has rolling mean family macro-F1 0.286, mean soft Brier score 0.463, and a persistence win rate of 28.6%.

## Bootstrap margin versus persistence

- Mean confidence-weighted monthly margin: -0.0194
- Lower confidence bound: -0.0556
- Upper confidence bound: 0.0414

## Prospective shadow isolation

| prospective_shadow_start   |   available_shadow_months | first_shadow_month   | last_shadow_month   | selection_contains_shadow_month   | consumed_audit_contains_shadow_month   | prospective_isolation_pass   |
|:---------------------------|--------------------------:|:---------------------|:--------------------|:----------------------------------|:---------------------------------------|:-----------------------------|
| 2026-04-30                 |                         0 |                      |                     | False                             | False                                  | True                         |

## Governance checks

| check_id                        | passed   |   observed |   threshold | interpretation                                                                             |
|:--------------------------------|:---------|-----------:|------------:|:-------------------------------------------------------------------------------------------|
| initial_release_completeness    | True     |  1         |        1    | Initial-release target states must be complete and explicitly dated.                       |
| fixed_horizon_completeness      | True     |  0.958904  |        0.8  | The fixed 90-day target requires sufficient cached-vintage coverage.                       |
| latest_revised_completeness     | True     |  1         |        0.95 | Latest-revised target states must be sufficiently complete.                                |
| initial_latest_family_agreement | False    |  0.712329  |        0.8  | Initial-release and latest-revised soft primary families should agree.                     |
| soft_target_confidence          | True     |  0.809403  |        0.65 | Soft family targets should assign adequate probability to the primary family.              |
| soft_target_ambiguity           | True     |  0.246575  |        0.4  | The share of structurally ambiguous family labels should remain limited.                   |
| source_beats_persistence        | False    |  0.285714  |        0.6  | The five-family source forecast should beat lagged-target persistence in most folds.       |
| bootstrap_margin_positive       | False    | -0.0555996 |        0    | The block-bootstrap lower confidence bound versus persistence must be positive.            |
| prospective_shadow_isolation    | True     |  1         |        1    | Months from the prospective shadow start must remain outside selection and consumed audit. |

## Decision

Model 1D should not return to candidate selection unless the real-time target reconstruction is sufficiently complete, the soft five-family target is stable across vintages, and the source forecast beats persistence with a strictly positive bootstrap lower margin. Months beginning with the prospective shadow date remain external evidence only.
