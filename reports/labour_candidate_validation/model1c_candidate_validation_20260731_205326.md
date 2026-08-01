# MacroPulse Model 1C v0.5 Candidate Validation

- Validation ID: `0540c6ee-2d96-493a-adfe-a76c5c91cf31`
- Backtest ID: `834e0655-ba81-4b96-b42c-e1cdda73b847`
- Interval calibration ID: `3576b19a-27b0-4ee4-bf59-910d9c821c1b`
- Prior vintage-validation ID: `94be6d19-51a2-4ba6-8956-a2d9d4e16df5`
- Status: **PASS**
- Stable point policy: **candidate**
- Adaptive policy: **shadow challenger only**
- Interval method: `exp_weighted_q80`

## Validation checks

| Gate | Check | Status | Observed | Threshold |
|---|---|---:|---:|---:|
| Operational reliability | Vintage evidence contains no unresolved hard issues | pass | 0 | 0 unresolved hard issues |
| Data availability | Structurally unavailable target months are explicitly documented | pass | 1 | documented exclusions allowed |
| Governance chain | A passing Model 1C vintage and interval validation is available | pass | available | passing validation required |
| Data integrity | One forecast per target, stage, month, and model | pass | 0 | 0 duplicates |
| Econometric validity | Forecast cutoff occurs before the initial target release | pass | 0 | 0 violations |
| Econometric validity | No observation is dated after the information cutoff | pass | 0 | 0 future-dated information sets |
| Econometric validity | Target-month outcome is absent before its initial release | pass | 0 | 0 leaked forecasts |
| Reproducibility | Every forecast has a valid information-set hash | pass | 0 | 0 invalid hashes |
| Data integrity | Every information set contains all declared baseline models | pass | 0 | 0 incomplete groups |
| Data integrity | All three targets and five declared stages are represented | pass | 0 | 0 incomplete target/stage maps |
| Econometric validity | Every generated forecast satisfies the training minimum | pass | 120 | >= 120 months |
| Econometric validity | Every forecast has positive lead time to the employment release | pass | 0 | 0 non-positive lead times |
| Performance reporting | Robust error, direction, and regime fields are complete | pass | 0 | 0 incomplete rows |
| Performance reporting | All declared economic regimes are represented for every target | pass | 0 | 0 incomplete targets |
| Policy governance | Stable candidate contains one predeclared decision for every target and stage | pass | 15 | 15 decisions |
| Policy governance | Stable candidate selects exactly one available component per information set | pass | 1739 selected rows; 0 duplicates | 1739 rows and 0 duplicates |
| Econometric validity | Stable candidate has sufficient evaluated history at every target and stage | pass | 109 | >= 100 months |
| Econometric validity | Stable candidate RMSE is competitive with the best static model | pass | 1.048183 | <= 1.060 |
| Econometric validity | Stable candidate MAE is competitive with the best static model | pass | 1.101855 | <= 1.120 |
| Econometric validity | Stable candidate median absolute error remains bounded | pass | 1.891345 | <= 2.000 |
| Econometric validity | Stable candidate upper-tail error is competitive among accuracy-eligible models | pass | 1.237408 | <= 1.250 |
| Econometric validity | Stable candidate maximum error is competitive among accuracy-and-tail-eligible models | pass | 1.118276 | <= 1.200 |
| Econometric validity | Stable candidate directional accuracy remains close to the best static model | pass | 0.083333 | <= 0.100 |
| Econometric validity | Stable candidate bias is bounded in target-appropriate units | pass | 0 | 0 target-stage bias violations |
| Econometric validity | Stable candidate performance is reported with sufficient history in every regime | pass | 22 | >= 20 months per regime |
| Challenger governance | Fixed and shadow policies have a sufficient identical-month comparison sample | pass | 85 | >= 80 months |
| Econometric validity | Adaptive shadow selection uses strictly prior target-month errors | pass | 0 | 0 look-ahead violations |
| Challenger governance | Adaptive shadow does not broadly dominate the stable candidate | pass | 4 of 15 groups | <= 5 broad wins |
| Challenger governance | Adaptive shadow switching remains within the declared stability cap | pass | 6 | <= 6 switches per group |
| Uncertainty calibration | Predeclared prior-only interval method is available | pass | exp_weighted_q80 | exp_weighted_q80 |
| Data integrity | Stable-policy interval evidence contains one interval per eligible information set | pass | 0 | 0 duplicate intervals |
| Econometric validity | Selected intervals use strictly prior target-month errors | pass | 0 | 0 look-ahead violations |
| Uncertainty calibration | Selected intervals satisfy the prior-error warm-up | pass | 24 | >= 24 prior errors |
| Uncertainty calibration | Selected intervals cover every target-stage policy group | pass | 15 | 15 target-stage groups |
| Uncertainty calibration | Selected intervals have sufficient stage-level evaluation history | pass | 85 | >= 80 months |
| Uncertainty calibration | Selected 80% intervals have acceptable aggregate empirical coverage | pass | 0.808557 | between 0.76 and 0.88 |
| Uncertainty calibration | Selected 80% intervals have acceptable coverage at every target and stage | pass | 0 groups outside range | each group between 0.75 and 0.90 |
| Operational reliability | Every selected interval has a finite positive half-width | pass | 0 | 0 invalid widths |
| Operational reliability | Every selected interval has a finite non-negative interval score | pass | 0 | 0 invalid scores |

## Stable candidate performance

| target_series | forecast_stage | observations | rmse | mae | bias | median_ae | p90_abs_error | max_abs_error | directional_accuracy | model_name |
|---|---|---|---|---|---|---|---|---|---|---|
| CES0500000003 | after_week_1 | 109 | 3.6299 | 1.9743 | 0.3137 | 1.2170 | 3.7177 | 27.7800 | 0.9358 | Labour Bridge Ridge |
| CES0500000003 | after_week_2 | 110 | 5.2855 | 2.0281 | 0.7581 | 1.0607 | 4.1404 | 49.1454 | 0.9545 | Labour Equal-Weight Ensemble |
| CES0500000003 | month_end | 110 | 5.4720 | 2.0329 | 0.7650 | 1.0475 | 4.0910 | 51.3582 | 0.9545 | Labour Equal-Weight Ensemble |
| CES0500000003 | month_open | 109 | 4.2693 | 2.0843 | 0.4194 | 1.2253 | 3.6209 | 34.7234 | 0.9358 | Labour Bridge Ridge |
| CES0500000003 | pre_employment_report | 110 | 5.4994 | 2.0492 | 0.7612 | 1.0387 | 4.1858 | 51.6288 | 0.9545 | Labour Equal-Weight Ensemble |
| PAYEMS | after_week_1 | 119 | 1950.6037 | 437.1485 | -31.0351 | 104.8771 | 517.0895 | 19280.5658 | 0.9076 | Labour Equal-Weight Ensemble |
| PAYEMS | after_week_2 | 120 | 1980.9072 | 515.3544 | -59.5732 | 124.0043 | 623.0610 | 18688.9304 | 0.8417 | Labour Bridge Ridge |
| PAYEMS | month_end | 120 | 1969.3515 | 507.9411 | -50.4886 | 138.2258 | 583.5086 | 18457.4908 | 0.8417 | Labour Bridge Ridge |
| PAYEMS | month_open | 119 | 2038.5438 | 481.7752 | -11.8102 | 73.0833 | 1067.8167 | 20678.0833 | 0.8655 | Labour 12-Month Mean |
| PAYEMS | pre_employment_report | 120 | 1964.7235 | 510.7692 | -47.5829 | 140.1573 | 672.6866 | 18405.2424 | 0.8667 | Labour Bridge Ridge |
| UNRATE | after_week_1 | 118 | 1.4121 | 0.4352 | 0.2328 | 0.1681 | 0.4723 | 11.6902 | 0.4831 | Labour Equal-Weight Ensemble |
| UNRATE | after_week_2 | 119 | 1.1361 | 0.3586 | 0.1741 | 0.1850 | 0.4333 | 11.1751 | 0.4706 | Labour Equal-Weight Ensemble |
| UNRATE | month_end | 119 | 1.0804 | 0.3472 | 0.1700 | 0.1874 | 0.4420 | 10.7554 | 0.4874 | Labour Equal-Weight Ensemble |
| UNRATE | month_open | 118 | 1.7569 | 0.5191 | 0.1394 | 0.2141 | 0.5330 | 12.0738 | 0.5254 | Labour Equal-Weight Ensemble |
| UNRATE | pre_employment_report | 119 | 1.0735 | 0.3392 | 0.1686 | 0.1829 | 0.4402 | 10.7004 | 0.5042 | Labour Equal-Weight Ensemble |

## Fixed versus adaptive shadow on identical months

| target_series | forecast_stage | fixed_observations | fixed_rmse | fixed_mae | fixed_bias | fixed_median_ae | fixed_p90_abs_error | fixed_max_abs_error | fixed_directional_accuracy | fixed_model_name | shadow_observations | shadow_rmse | shadow_mae | shadow_bias | shadow_median_ae | shadow_p90_abs_error | shadow_max_abs_error | shadow_directional_accuracy | shadow_model_name | shadow_to_fixed_rmse_ratio | shadow_to_fixed_mae_ratio | shadow_to_fixed_p90_abs_error_ratio | shadow_to_fixed_max_abs_error_ratio | absolute_bias_improved | directional_accuracy_improved | shadow_rmse_improved | shadow_mae_improved | shadow_tail_improved |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CES0500000003 | after_week_1 | 85 | 4.0359 | 2.1807 | 0.3673 | 1.2548 | 4.2972 | 27.7800 | 0.9294 | Labour Bridge Ridge | 85 | 5.6323 | 2.4111 | 0.6698 | 1.1263 | 4.2972 | 43.5371 | 0.9294 | Adaptive shadow | 1.3955 | 1.1056 | 1.0000 | 1.5672 | False | False | False | False | False |
| CES0500000003 | after_week_2 | 86 | 5.9343 | 2.2786 | 0.8865 | 1.0492 | 4.3552 | 49.1454 | 0.9535 | Labour Equal-Weight Ensemble | 86 | 6.1175 | 2.3220 | 0.8662 | 1.0004 | 4.3552 | 50.8902 | 0.9535 | Adaptive shadow | 1.0309 | 1.0191 | 1.0000 | 1.0355 | True | False | False | False | False |
| CES0500000003 | month_end | 86 | 6.1466 | 2.2789 | 0.9011 | 1.0637 | 4.4021 | 51.3582 | 0.9535 | Labour Equal-Weight Ensemble | 86 | 6.6242 | 2.5196 | 0.7009 | 1.0819 | 4.4021 | 51.8969 | 0.9419 | Adaptive shadow | 1.0777 | 1.1057 | 1.0000 | 1.0105 | True | False | False | False | False |
| CES0500000003 | month_open | 85 | 4.7418 | 2.2607 | 0.4942 | 1.2917 | 4.1469 | 34.7234 | 0.9294 | Labour Bridge Ridge | 85 | 6.5340 | 2.5516 | 0.8723 | 1.1075 | 4.6301 | 50.4627 | 0.9412 | Adaptive shadow | 1.3780 | 1.1287 | 1.1165 | 1.4533 | False | True | False | False | False |
| CES0500000003 | pre_employment_report | 86 | 6.1780 | 2.2994 | 0.8979 | 1.0384 | 4.3163 | 51.6288 | 0.9535 | Labour Equal-Weight Ensemble | 86 | 6.6235 | 2.5221 | 0.7289 | 1.0510 | 4.3163 | 51.8969 | 0.9419 | Adaptive shadow | 1.0721 | 1.0969 | 1.0000 | 1.0052 | True | False | False | False | False |
| PAYEMS | after_week_1 | 95 | 2182.7271 | 530.9660 | -30.8684 | 117.4698 | 632.2791 | 19280.5658 | 0.8947 | Labour Equal-Weight Ensemble | 95 | 2264.6233 | 564.8812 | 72.8352 | 125.0000 | 880.6539 | 20696.0000 | 0.9053 | Adaptive shadow | 1.0375 | 1.0639 | 1.3928 | 1.0734 | False | True | False | False | False |
| PAYEMS | after_week_2 | 96 | 2214.2177 | 625.6377 | -68.1320 | 157.2657 | 818.2446 | 18688.9304 | 0.8125 | Labour Bridge Ridge | 96 | 2302.9100 | 596.9917 | 55.4477 | 106.8333 | 1086.6250 | 20696.0000 | 0.8125 | Adaptive shadow | 1.0401 | 0.9542 | 1.3280 | 1.1074 | True | False | False | True | False |
| PAYEMS | month_end | 96 | 2201.1867 | 614.4687 | -53.5230 | 152.7934 | 821.7577 | 18457.4908 | 0.8125 | Labour Bridge Ridge | 96 | 2304.8750 | 601.9050 | 53.1559 | 105.4167 | 1086.6250 | 20696.0000 | 0.7917 | Adaptive shadow | 1.0471 | 0.9796 | 1.3223 | 1.1213 | True | False | False | True | False |
| PAYEMS | month_open | 95 | 2281.2914 | 589.9614 | -12.4754 | 100.5833 | 1254.6167 | 20678.0833 | 0.8421 | Labour 12-Month Mean | 95 | 2281.7702 | 596.0212 | 7.0260 | 118.0619 | 1254.6167 | 20678.0833 | 0.8316 | Adaptive shadow | 1.0002 | 1.0103 | 1.0000 | 1.0000 | True | False | False | False | False |
| PAYEMS | pre_employment_report | 96 | 2196.0315 | 618.0145 | -49.7590 | 163.1339 | 826.1793 | 18405.2424 | 0.8438 | Labour Bridge Ridge | 96 | 2305.2688 | 605.7259 | 56.2009 | 110.0565 | 1086.6250 | 20696.0000 | 0.7812 | Adaptive shadow | 1.0497 | 0.9801 | 1.3152 | 1.1245 | False | False | False | True | False |
| UNRATE | after_week_1 | 94 | 1.5803 | 0.5135 | 0.2731 | 0.2375 | 0.5114 | 11.6902 | 0.4787 | Labour Equal-Weight Ensemble | 94 | 1.5768 | 0.4893 | 0.2130 | 0.1813 | 0.4971 | 11.6902 | 0.4787 | Adaptive shadow | 0.9978 | 0.9528 | 0.9720 | 1.0000 | True | False | True | True | True |
| UNRATE | after_week_2 | 95 | 1.2694 | 0.4176 | 0.1982 | 0.2384 | 0.4628 | 11.1751 | 0.4737 | Labour Equal-Weight Ensemble | 95 | 1.2654 | 0.3976 | 0.1495 | 0.1850 | 0.4494 | 11.1751 | 0.4632 | Adaptive shadow | 0.9969 | 0.9520 | 0.9712 | 1.0000 | True | False | True | True | True |
| UNRATE | month_end | 95 | 1.2069 | 0.4034 | 0.1936 | 0.2210 | 0.4516 | 10.7554 | 0.4947 | Labour Equal-Weight Ensemble | 95 | 1.2022 | 0.3793 | 0.1324 | 0.1815 | 0.4438 | 10.7554 | 0.4842 | Adaptive shadow | 0.9961 | 0.9401 | 0.9828 | 1.0000 | True | False | True | True | True |
| UNRATE | month_open | 94 | 1.9668 | 0.6164 | 0.1609 | 0.2449 | 0.5745 | 12.0738 | 0.5000 | Labour Equal-Weight Ensemble | 94 | 2.7925 | 0.6957 | -0.0299 | 0.2045 | 0.5592 | 22.4605 | 0.4894 | Adaptive shadow | 1.4198 | 1.1286 | 0.9733 | 1.8603 | True | False | False | False | True |
| UNRATE | pre_employment_report | 95 | 1.1991 | 0.3933 | 0.1918 | 0.2046 | 0.4442 | 10.7004 | 0.5158 | Labour Equal-Weight Ensemble | 95 | 1.1937 | 0.3598 | 0.1211 | 0.1744 | 0.4411 | 10.7004 | 0.5158 | Adaptive shadow | 0.9955 | 0.9149 | 0.9929 | 1.0000 | True | False | True | True | True |

## Shadow switching stability

| target_series | forecast_stage | eligible_months | switches | distinct_selected_models | stable_policy_share | most_selected_model |
|---|---|---|---|---|---|---|
| CES0500000003 | after_week_1 | 85 | 5 | 4 | 0.4235 | Labour Bridge Ridge |
| CES0500000003 | after_week_2 | 86 | 5 | 3 | 0.5814 | Labour Equal-Weight Ensemble |
| CES0500000003 | month_end | 86 | 6 | 4 | 0.6163 | Labour Equal-Weight Ensemble |
| CES0500000003 | month_open | 85 | 4 | 3 | 0.0000 | Labour Equal-Weight Ensemble |
| CES0500000003 | pre_employment_report | 86 | 5 | 3 | 0.6628 | Labour Equal-Weight Ensemble |
| PAYEMS | after_week_1 | 95 | 4 | 3 | 0.0421 | Labour 12-Month Mean |
| PAYEMS | after_week_2 | 96 | 5 | 4 | 0.0000 | Labour 12-Month Mean |
| PAYEMS | month_end | 96 | 4 | 3 | 0.0000 | Labour 12-Month Mean |
| PAYEMS | month_open | 95 | 5 | 3 | 0.8526 | Labour 12-Month Mean |
| PAYEMS | pre_employment_report | 96 | 4 | 3 | 0.0000 | Labour 12-Month Mean |
| UNRATE | after_week_1 | 94 | 1 | 2 | 0.8191 | Labour Equal-Weight Ensemble |
| UNRATE | after_week_2 | 95 | 1 | 2 | 0.8526 | Labour Equal-Weight Ensemble |
| UNRATE | month_end | 95 | 3 | 3 | 0.7895 | Labour Equal-Weight Ensemble |
| UNRATE | month_open | 94 | 4 | 3 | 0.6383 | Labour Equal-Weight Ensemble |
| UNRATE | pre_employment_report | 95 | 4 | 3 | 0.7368 | Labour Equal-Weight Ensemble |

## Stable candidate regime performance

| target_series | forecast_stage | regime | observations | rmse | mae | bias | median_ae | p90_abs_error | max_abs_error | directional_accuracy |
|---|---|---|---|---|---|---|---|---|---|---|
| CES0500000003 | after_week_1 | pandemic_dislocation | 22 | 7.4957 | 5.0297 | 2.7145 | 3.6464 | 8.1252 | 27.7800 | 0.7727 |
| CES0500000003 | after_week_1 | post_2021 | 54 | 1.5622 | 1.1871 | -0.4230 | 1.0435 | 2.6434 | 4.3353 | 1.0000 |
| CES0500000003 | after_week_1 | pre_pandemic | 33 | 1.4394 | 1.2253 | -0.0812 | 1.0819 | 2.4152 | 2.6933 | 0.9394 |
| CES0500000003 | after_week_2 | pandemic_dislocation | 22 | 11.4820 | 5.8277 | 3.3130 | 3.9405 | 9.4433 | 49.1454 | 0.8636 |
| CES0500000003 | after_week_2 | post_2021 | 54 | 1.4382 | 1.0701 | 0.1119 | 0.8378 | 2.0590 | 5.2699 | 1.0000 |
| CES0500000003 | after_week_2 | pre_pandemic | 34 | 1.3380 | 1.0911 | 0.1312 | 0.9803 | 2.0898 | 2.8901 | 0.9412 |
| CES0500000003 | month_end | pandemic_dislocation | 22 | 11.9170 | 5.8444 | 3.3518 | 3.9736 | 7.2227 | 51.3582 | 0.8636 |
| CES0500000003 | month_end | post_2021 | 54 | 1.4336 | 1.0820 | 0.1153 | 0.8840 | 2.0561 | 5.1392 | 1.0000 |
| CES0500000003 | month_end | pre_pandemic | 34 | 1.3106 | 1.0769 | 0.1232 | 0.9626 | 2.0377 | 2.7294 | 0.9412 |
| CES0500000003 | month_open | pandemic_dislocation | 22 | 8.8838 | 5.1986 | 3.1472 | 3.0652 | 10.0949 | 34.7234 | 0.7727 |
| CES0500000003 | month_open | post_2021 | 54 | 1.6995 | 1.2373 | -0.3878 | 0.9942 | 2.7558 | 6.2016 | 1.0000 |
| CES0500000003 | month_open | pre_pandemic | 33 | 1.6917 | 1.3940 | -0.0784 | 1.1500 | 2.6014 | 4.8800 | 0.9394 |
| CES0500000003 | pre_employment_report | pandemic_dislocation | 22 | 11.9810 | 5.9196 | 3.3423 | 4.0293 | 7.2546 | 51.6288 | 0.8636 |
| CES0500000003 | pre_employment_report | post_2021 | 54 | 1.4314 | 1.0857 | 0.1136 | 0.9181 | 2.1123 | 5.1847 | 1.0000 |
| CES0500000003 | pre_employment_report | pre_pandemic | 34 | 1.3079 | 1.0751 | 0.1195 | 0.9478 | 2.0213 | 2.7265 | 0.9412 |
| PAYEMS | after_week_1 | pandemic_dislocation | 22 | 4525.6166 | 1889.3350 | -246.8773 | 527.0485 | 3315.7234 | 19280.5658 | 0.7273 |
| PAYEMS | after_week_1 | post_2021 | 54 | 186.1322 | 140.1580 | 49.2063 | 113.0404 | 254.8631 | 653.0763 | 0.9259 |
| PAYEMS | after_week_1 | pre_pandemic | 43 | 86.3136 | 67.1341 | -21.3725 | 58.4338 | 156.3189 | 206.0751 | 0.9767 |
| PAYEMS | after_week_2 | pandemic_dislocation | 22 | 4609.3613 | 2195.9854 | -310.6602 | 703.9966 | 5038.2568 | 18688.9304 | 0.6818 |
| PAYEMS | after_week_2 | post_2021 | 54 | 236.7650 | 184.7035 | 3.0635 | 154.5294 | 385.2814 | 747.2484 | 0.7963 |
| PAYEMS | after_week_2 | pre_pandemic | 44 | 99.4808 | 80.8377 | -10.9020 | 72.4050 | 165.2690 | 236.9125 | 0.9773 |
| PAYEMS | month_end | pandemic_dislocation | 22 | 4582.0703 | 2157.3950 | -250.8583 | 602.2814 | 4680.7145 | 18457.4908 | 0.7273 |
| PAYEMS | month_end | post_2021 | 54 | 235.3210 | 178.7815 | 2.1918 | 152.0546 | 350.5082 | 825.6161 | 0.7778 |
| PAYEMS | month_end | pre_pandemic | 44 | 107.9832 | 87.1829 | -14.9571 | 73.4453 | 173.5873 | 249.5635 | 0.9773 |
| PAYEMS | month_open | pandemic_dislocation | 22 | 4736.3067 | 2251.0455 | 95.3636 | 1109.9583 | 3376.9333 | 20678.0833 | 0.4091 |
| PAYEMS | month_open | post_2021 | 54 | 119.4029 | 97.5802 | -56.5864 | 72.2500 | 207.3917 | 249.4167 | 0.9630 |
| PAYEMS | month_open | pre_pandemic | 43 | 74.1704 | 59.0446 | -10.4128 | 48.0833 | 99.5333 | 217.9167 | 0.9767 |
| PAYEMS | pre_employment_report | pandemic_dislocation | 22 | 4571.7883 | 2167.0413 | -243.1118 | 715.6218 | 4598.8978 | 18405.2424 | 0.7727 |
| PAYEMS | pre_employment_report | post_2021 | 54 | 230.9636 | 181.1282 | 4.9198 | 163.1339 | 346.6946 | 799.3608 | 0.8148 |
| PAYEMS | pre_employment_report | pre_pandemic | 44 | 107.5103 | 87.1926 | -14.2536 | 73.4040 | 178.3469 | 241.4196 | 0.9773 |
| UNRATE | after_week_1 | pandemic_dislocation | 22 | 3.2333 | 1.4774 | 0.5496 | 0.4230 | 4.0986 | 11.6902 | 0.8636 |
| UNRATE | after_week_1 | post_2021 | 53 | 0.2739 | 0.2383 | 0.2066 | 0.2360 | 0.4228 | 0.5255 | 0.3208 |
| UNRATE | after_week_1 | pre_pandemic | 43 | 0.1757 | 0.1448 | 0.1031 | 0.1229 | 0.2715 | 0.4489 | 0.4884 |
| UNRATE | after_week_2 | pandemic_dislocation | 22 | 2.5958 | 1.0727 | 0.2239 | 0.3731 | 1.1983 | 11.1751 | 0.8636 |
| UNRATE | after_week_2 | post_2021 | 53 | 0.2777 | 0.2432 | 0.2090 | 0.2391 | 0.4314 | 0.5255 | 0.3208 |
| UNRATE | after_week_2 | pre_pandemic | 44 | 0.1701 | 0.1406 | 0.1071 | 0.1198 | 0.2514 | 0.4650 | 0.4545 |
| UNRATE | month_end | pandemic_dislocation | 22 | 2.4656 | 1.0323 | 0.2066 | 0.3717 | 1.3406 | 10.7554 | 0.9091 |
| UNRATE | month_end | post_2021 | 53 | 0.2718 | 0.2375 | 0.2090 | 0.2279 | 0.4292 | 0.5282 | 0.3208 |
| UNRATE | month_end | pre_pandemic | 44 | 0.1687 | 0.1368 | 0.1048 | 0.1161 | 0.2505 | 0.4677 | 0.4773 |
| UNRATE | month_open | pandemic_dislocation | 22 | 4.0369 | 1.9052 | 0.0900 | 0.4672 | 7.7833 | 12.0738 | 0.8182 |
| UNRATE | month_open | post_2021 | 53 | 0.2859 | 0.2476 | 0.2056 | 0.2391 | 0.4490 | 0.6151 | 0.3585 |
| UNRATE | month_open | pre_pandemic | 43 | 0.1797 | 0.1446 | 0.0830 | 0.1358 | 0.2828 | 0.4412 | 0.5814 |
| UNRATE | pre_employment_report | pandemic_dislocation | 22 | 2.4524 | 1.0147 | 0.2193 | 0.3267 | 1.3474 | 10.7004 | 0.9091 |
| UNRATE | pre_employment_report | post_2021 | 53 | 0.2594 | 0.2268 | 0.2005 | 0.2242 | 0.3950 | 0.4874 | 0.3585 |
| UNRATE | pre_employment_report | pre_pandemic | 44 | 0.1688 | 0.1368 | 0.1050 | 0.1140 | 0.2538 | 0.4677 | 0.4773 |

## Selected interval diagnostics — exp_weighted_q80

| target_series | forecast_stage | observations | coverage | average_half_width | mean_interval_score | median_interval_score | minimum_prior_errors |
|---|---|---|---|---|---|---|---|
| CES0500000003 | after_week_1 | 85 | 0.8235 | 3.2626 | 12.5310 | 6.7891 | 24 |
| CES0500000003 | after_week_2 | 86 | 0.8023 | 2.9001 | 14.6599 | 5.6828 | 24 |
| CES0500000003 | month_end | 86 | 0.7907 | 2.8801 | 14.5648 | 5.8927 | 24 |
| CES0500000003 | month_open | 85 | 0.8235 | 3.1577 | 14.0059 | 5.9280 | 24 |
| CES0500000003 | pre_employment_report | 86 | 0.8023 | 2.9090 | 14.6474 | 6.1402 | 24 |
| PAYEMS | after_week_1 | 95 | 0.8211 | 435.3475 | 4399.8013 | 717.6078 | 24 |
| PAYEMS | after_week_2 | 96 | 0.8333 | 598.2290 | 4921.0061 | 791.9595 | 24 |
| PAYEMS | month_end | 96 | 0.8229 | 598.0780 | 4910.3983 | 718.6511 | 24 |
| PAYEMS | month_open | 95 | 0.8421 | 654.9237 | 4630.0228 | 498.8333 | 24 |
| PAYEMS | pre_employment_report | 96 | 0.8333 | 602.9094 | 4905.6108 | 738.0664 | 24 |
| UNRATE | after_week_1 | 94 | 0.7766 | 0.4676 | 3.6383 | 0.8546 | 24 |
| UNRATE | after_week_2 | 95 | 0.7895 | 0.4084 | 2.7489 | 0.8274 | 24 |
| UNRATE | month_end | 95 | 0.7789 | 0.4118 | 2.6507 | 0.8378 | 24 |
| UNRATE | month_open | 94 | 0.7979 | 0.4757 | 4.6073 | 0.9037 | 24 |
| UNRATE | pre_employment_report | 95 | 0.7895 | 0.3947 | 2.6301 | 0.7537 | 24 |

## Governance conclusion

The stable 15-decision target-stage map is the Model 1C point-forecast candidate. The adaptive selector remains shadow-only: its broad gains are concentrated in unemployment-rate groups, while it materially worsens earnings and payroll comparisons on the same eligible months. The selected prior-only exponentially weighted empirical 80% intervals have acceptable aggregate and target-stage coverage. This validation is not a production freeze: governed live forecasts, provenance signatures, labour-news decomposition, and operational validation remain required.