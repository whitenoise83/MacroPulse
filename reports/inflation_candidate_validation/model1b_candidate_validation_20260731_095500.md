# MacroPulse Model 1B v0.5 Candidate Validation

- Validation ID: `5f0cd6ea-c41f-44da-a21a-43490d8e75ce`
- Backtest ID: `fdd2f573-a425-4abc-8056-f9843955bac2`
- Status: **PASS**
- Stable point policy: **candidate**
- Adaptive policy: **shadow challenger only**
- Interval method: `exp_weighted_q80`

## Validation checks

| Gate | Check | Status | Observed | Threshold |
|---|---|---:|---:|---:|
| Data integrity | One forecast per target, stage, month, and model | pass | 0 | 0 duplicates |
| Econometric validity | Forecast cutoff occurs before the initial target release | pass | 0 | 0 violations |
| Econometric validity | No observation is dated after the information cutoff | pass | 0 | 0 future-dated information sets |
| Econometric validity | Target-month index is absent before its initial release | pass | 0 | 0 leaked forecasts |
| Reproducibility | Every forecast has a valid information-set hash | pass | 0 | 0 invalid hashes |
| Data integrity | Every information set contains all declared baseline models | pass | 0 | 0 incomplete groups |
| Data integrity | All four targets and four declared stages are represented | pass | 0 | 0 incomplete target/stage maps |
| Econometric validity | Every generated forecast satisfies the training minimum | pass | 120 | >= 120 months |
| Policy governance | Stable candidate contains one predeclared decision for every target and stage | pass | 16 | 16 decisions |
| Policy governance | Stable candidate selects exactly one available component per information set | pass | 1202 selected rows; 0 duplicates | 1202 rows and 0 duplicates |
| Econometric validity | Stable candidate has sufficient evaluated history at every target and stage | pass | 73 | >= 60 months |
| Econometric validity | Stable candidate RMSE is competitive with the best static model | pass | 1.011777 | <= 1.050 |
| Econometric validity | Stable candidate MAE is competitive with the best static model | pass | 1.027239 | <= 1.100 |
| Econometric validity | Stable candidate upper-tail error is competitive with the best static model | pass | 1.123937 | <= 1.150 |
| Econometric validity | Stable candidate maximum error is not materially worse than the best static model | pass | 1.148494 | <= 1.200 |
| Econometric validity | Stable candidate absolute bias is bounded at every target and stage | pass | 0.39883 | <= 0.750 annualised pp |
| Challenger governance | Fixed and shadow policies have a sufficient identical-month comparison sample | pass | 49 | >= 48 months |
| Econometric validity | Adaptive shadow selection uses strictly prior target-month errors | pass | 0 | 0 look-ahead violations |
| Challenger governance | Adaptive shadow does not broadly dominate the stable candidate | pass | 4 of 16 groups | <= 8 broad wins |
| Challenger governance | Adaptive shadow switching remains within the declared stability cap | pass | 6 | <= 6 switches per group |
| Uncertainty calibration | Predeclared selected interval method is available | pass | exp_weighted_q80 | exp_weighted_q80 |
| Econometric validity | Selected intervals use strictly prior target-month errors | pass | 0 | 0 look-ahead violations |
| Uncertainty calibration | Selected intervals satisfy the prior-error warm-up | pass | 24 | >= 24 prior errors |
| Uncertainty calibration | Selected intervals have sufficient stage-level evaluation history | pass | 49 | >= 48 months |
| Uncertainty calibration | Selected 80% intervals have acceptable aggregate empirical coverage | pass | 0.847188 | between 0.75 and 0.90 |
| Uncertainty calibration | Selected 80% intervals have acceptable coverage at every target and stage | pass | 0 groups outside range | each group between 0.75 and 0.95 |
| Uncertainty calibration | Selected interval method remains the interval-score winner | pass | 1.0 | <= 1.001 |
| Operational reliability | Every selected interval has a finite positive half-width | pass | 0 | 0 invalid widths |

## Stable candidate performance

| target_series | forecast_stage | observations | rmse | mae | bias | median_ae | p90_abs_error | max_abs_error | model_name |
|---|---|---|---|---|---|---|---|---|---|
| CPIAUCSL | mid_month | 76 | 3.5977 | 2.5104 | 0.1678 | 1.7373 | 6.2080 | 12.0455 | Inflation Ridge-AR Ensemble |
| CPIAUCSL | month_end | 76 | 3.6027 | 2.5144 | 0.1527 | 1.7045 | 6.1791 | 12.0455 | Inflation Ridge-AR Ensemble |
| CPIAUCSL | month_open | 74 | 4.0242 | 2.9041 | 0.2623 | 2.0751 | 6.3691 | 12.4333 | Inflation Ridge-AR Ensemble |
| CPIAUCSL | pre_release | 76 | 3.5860 | 2.5013 | 0.1464 | 1.6755 | 6.1827 | 12.0841 | Inflation Ridge-AR Ensemble |
| CPILFESL | mid_month | 76 | 2.1678 | 1.5495 | 0.2691 | 1.1371 | 3.6391 | 7.9057 | Inflation Ridge-AR Ensemble |
| CPILFESL | month_end | 76 | 2.1695 | 1.5510 | 0.2618 | 1.1075 | 3.6391 | 7.9057 | Inflation Ridge-AR Ensemble |
| CPILFESL | month_open | 74 | 2.6225 | 1.7974 | -0.0031 | 1.2223 | 3.4643 | 9.6749 | Inflation 12-Month Mean |
| CPILFESL | pre_release | 76 | 2.1638 | 1.5424 | 0.2572 | 1.0787 | 3.6353 | 7.9057 | Inflation Ridge-AR Ensemble |
| PCEPI | mid_month | 74 | 2.3724 | 1.7860 | 0.0502 | 1.2238 | 3.8612 | 7.0609 | Inflation Bridge Ridge |
| PCEPI | month_end | 76 | 2.3939 | 1.7179 | 0.0274 | 1.1130 | 3.9627 | 8.4291 | Inflation Bridge Ridge |
| PCEPI | month_open | 73 | 2.5848 | 2.0274 | 0.0862 | 1.5205 | 4.2423 | 7.4308 | Inflation Bridge Ridge |
| PCEPI | pre_release | 76 | 2.4035 | 1.7440 | -0.0286 | 1.1550 | 3.8931 | 8.3838 | Inflation Bridge Ridge |
| PCEPILFE | mid_month | 74 | 1.9188 | 1.4549 | 0.3800 | 1.0714 | 2.9695 | 6.4334 | Inflation Ridge-AR Ensemble |
| PCEPILFE | month_end | 76 | 1.8102 | 1.3255 | 0.3988 | 0.9218 | 2.8240 | 6.0026 | Inflation Ridge-AR Ensemble |
| PCEPILFE | month_open | 73 | 1.8755 | 1.4501 | 0.1769 | 1.2891 | 3.2421 | 5.9930 | Inflation Bridge Ridge |
| PCEPILFE | pre_release | 76 | 1.7935 | 1.3171 | 0.3911 | 0.9250 | 2.8234 | 5.9907 | Inflation Ridge-AR Ensemble |

## Fixed versus adaptive shadow on identical months

| target_series | forecast_stage | fixed_observations | fixed_rmse | fixed_mae | fixed_bias | fixed_median_ae | fixed_p90_abs_error | fixed_max_abs_error | fixed_model_name | shadow_observations | shadow_rmse | shadow_mae | shadow_bias | shadow_median_ae | shadow_p90_abs_error | shadow_max_abs_error | shadow_model_name | shadow_to_fixed_rmse_ratio | shadow_to_fixed_mae_ratio | shadow_to_fixed_p90_abs_error_ratio | shadow_to_fixed_max_abs_error_ratio | absolute_bias_improved | shadow_rmse_improved | shadow_mae_improved | shadow_tail_improved |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CPIAUCSL | mid_month | 52 | 3.7638 | 2.5449 | -0.1876 | 1.7373 | 6.6046 | 12.0455 | Inflation Ridge-AR Ensemble | 52 | 3.9140 | 2.6043 | -0.2032 | 1.3215 | 6.8381 | 12.7183 | Adaptive shadow | 1.0399 | 1.0233 | 1.0354 | 1.0559 | False | False | False | False |
| CPIAUCSL | month_end | 52 | 3.7710 | 2.5521 | -0.2107 | 1.7045 | 6.5911 | 12.0455 | Inflation Ridge-AR Ensemble | 52 | 3.9210 | 2.5957 | -0.2120 | 1.2747 | 6.8381 | 12.7183 | Adaptive shadow | 1.0398 | 1.0171 | 1.0375 | 1.0559 | False | False | False | False |
| CPIAUCSL | month_open | 50 | 4.0774 | 2.8150 | -0.2193 | 1.9892 | 6.4411 | 12.4333 | Inflation Ridge-AR Ensemble | 50 | 4.0507 | 2.8336 | -0.2809 | 2.0735 | 6.4411 | 12.4333 | Adaptive shadow | 0.9934 | 1.0066 | 1.0000 | 1.0000 | False | True | False | False |
| CPIAUCSL | pre_release | 52 | 3.7572 | 2.5510 | -0.2206 | 1.6755 | 6.6134 | 12.0841 | Inflation Ridge-AR Ensemble | 52 | 3.9200 | 2.6095 | -0.2240 | 1.2747 | 6.8629 | 12.7956 | Adaptive shadow | 1.0433 | 1.0229 | 1.0377 | 1.0589 | False | False | False | False |
| CPILFESL | mid_month | 52 | 1.5993 | 1.2434 | 0.0954 | 1.0478 | 2.7644 | 3.8023 | Inflation Ridge-AR Ensemble | 52 | 1.5334 | 1.2084 | 0.1896 | 1.0478 | 2.6069 | 3.7891 | Adaptive shadow | 0.9588 | 0.9719 | 0.9430 | 0.9965 | False | True | True | True |
| CPILFESL | month_end | 52 | 1.6027 | 1.2460 | 0.0852 | 0.9942 | 2.7644 | 3.8023 | Inflation Ridge-AR Ensemble | 52 | 1.5354 | 1.2056 | 0.1867 | 0.9973 | 2.6069 | 3.7891 | Adaptive shadow | 0.9580 | 0.9675 | 0.9430 | 0.9965 | False | True | True | True |
| CPILFESL | month_open | 50 | 1.5757 | 1.2038 | -0.5742 | 0.8246 | 2.7846 | 4.0637 | Inflation 12-Month Mean | 50 | 1.8438 | 1.3787 | -0.2385 | 0.9878 | 3.2035 | 4.7073 | Adaptive shadow | 1.1702 | 1.1453 | 1.1504 | 1.1584 | True | False | False | False |
| CPILFESL | pre_release | 52 | 1.5884 | 1.2362 | 0.0703 | 1.0078 | 2.7646 | 3.7867 | Inflation Ridge-AR Ensemble | 52 | 1.5285 | 1.2089 | 0.1883 | 1.0638 | 2.6071 | 3.7779 | Adaptive shadow | 0.9623 | 0.9779 | 0.9430 | 0.9977 | False | True | True | True |
| PCEPI | mid_month | 50 | 2.5131 | 1.8875 | -0.2824 | 1.2966 | 4.3517 | 7.0609 | Inflation Bridge Ridge | 50 | 2.5443 | 1.8923 | -0.1712 | 1.3055 | 4.3944 | 7.0609 | Adaptive shadow | 1.0124 | 1.0026 | 1.0098 | 1.0000 | True | False | False | False |
| PCEPI | month_end | 52 | 2.5902 | 1.8560 | -0.2470 | 1.1615 | 4.5216 | 8.4291 | Inflation Bridge Ridge | 52 | 2.6284 | 1.9029 | 0.0340 | 1.3786 | 4.7138 | 8.4291 | Adaptive shadow | 1.0147 | 1.0253 | 1.0425 | 1.0000 | True | False | False | False |
| PCEPI | month_open | 49 | 2.6056 | 1.9733 | -0.2709 | 1.4610 | 4.4988 | 7.4308 | Inflation Bridge Ridge | 49 | 2.6305 | 1.9217 | -0.1543 | 1.4142 | 4.6423 | 7.4308 | Adaptive shadow | 1.0095 | 0.9739 | 1.0319 | 1.0000 | True | False | True | False |
| PCEPI | pre_release | 52 | 2.6061 | 1.9025 | -0.3310 | 1.2438 | 4.3672 | 8.3838 | Inflation Bridge Ridge | 52 | 2.5376 | 1.8189 | -0.0689 | 1.2226 | 4.0460 | 8.3838 | Adaptive shadow | 0.9737 | 0.9561 | 0.9264 | 1.0000 | True | True | True | True |
| PCEPILFE | mid_month | 50 | 1.6528 | 1.2184 | 0.1449 | 0.9613 | 2.7593 | 5.0149 | Inflation Ridge-AR Ensemble | 50 | 1.6478 | 1.2818 | -0.1295 | 0.9632 | 2.6277 | 5.0149 | Adaptive shadow | 0.9970 | 1.0521 | 0.9523 | 1.0000 | True | True | False | True |
| PCEPILFE | month_end | 52 | 1.6102 | 1.1243 | 0.1787 | 0.6676 | 2.8464 | 4.7398 | Inflation Ridge-AR Ensemble | 52 | 1.7261 | 1.2850 | -0.0920 | 0.8639 | 2.6870 | 4.8604 | Adaptive shadow | 1.0720 | 1.1429 | 0.9440 | 1.0254 | True | False | False | True |
| PCEPILFE | month_open | 49 | 1.6861 | 1.3155 | -0.1605 | 1.0327 | 3.1025 | 4.0954 | Inflation Bridge Ridge | 49 | 1.6613 | 1.3271 | -0.3187 | 1.0325 | 2.7460 | 4.0954 | Adaptive shadow | 0.9853 | 1.0088 | 0.8851 | 1.0000 | False | True | False | True |
| PCEPILFE | pre_release | 52 | 1.5825 | 1.1166 | 0.1675 | 0.6873 | 2.7804 | 4.7406 | Inflation Ridge-AR Ensemble | 52 | 1.6972 | 1.2563 | -0.1438 | 0.7597 | 2.6870 | 4.9362 | Adaptive shadow | 1.0725 | 1.1251 | 0.9664 | 1.0413 | True | False | False | True |

## Shadow switching stability

| target_series | forecast_stage | eligible_months | switches | distinct_selected_models | stable_policy_share | most_selected_model |
|---|---|---|---|---|---|---|
| CPIAUCSL | mid_month | 52 | 3 | 3 | 0.0000 | Inflation Bridge Ridge |
| CPIAUCSL | month_end | 52 | 3 | 3 | 0.0000 | Inflation Bridge Ridge |
| CPIAUCSL | month_open | 50 | 3 | 3 | 0.5200 | Inflation Ridge-AR Ensemble |
| CPIAUCSL | pre_release | 52 | 3 | 3 | 0.0000 | Inflation Bridge Ridge |
| CPILFESL | mid_month | 52 | 3 | 3 | 0.5192 | Inflation Ridge-AR Ensemble |
| CPILFESL | month_end | 52 | 3 | 3 | 0.5192 | Inflation Ridge-AR Ensemble |
| CPILFESL | month_open | 50 | 2 | 2 | 0.7200 | Inflation 12-Month Mean |
| CPILFESL | pre_release | 52 | 4 | 3 | 0.6154 | Inflation Ridge-AR Ensemble |
| PCEPI | mid_month | 50 | 3 | 3 | 0.8200 | Inflation Bridge Ridge |
| PCEPI | month_end | 52 | 6 | 4 | 0.5192 | Inflation Bridge Ridge |
| PCEPI | month_open | 49 | 3 | 3 | 0.8367 | Inflation Bridge Ridge |
| PCEPI | pre_release | 52 | 4 | 4 | 0.5000 | Inflation Bridge Ridge |
| PCEPILFE | mid_month | 50 | 1 | 2 | 0.2800 | Inflation 12-Month Mean |
| PCEPILFE | month_end | 52 | 2 | 3 | 0.0962 | Inflation 12-Month Mean |
| PCEPILFE | month_open | 49 | 1 | 2 | 0.2857 | Inflation 12-Month Mean |
| PCEPILFE | pre_release | 52 | 4 | 3 | 0.1538 | Inflation 12-Month Mean |

## Selected interval diagnostics — exp_weighted_q80

| target_series | forecast_stage | observations | coverage | average_half_width | mean_interval_score |
|---|---|---|---|---|---|
| CPIAUCSL | mid_month | 52 | 0.8269 | 4.5949 | 14.1629 |
| CPIAUCSL | month_end | 52 | 0.8462 | 4.6205 | 14.1910 |
| CPIAUCSL | month_open | 50 | 0.8600 | 5.0108 | 15.2327 |
| CPIAUCSL | pre_release | 52 | 0.8269 | 4.5426 | 14.2318 |
| CPILFESL | mid_month | 52 | 0.8846 | 2.5764 | 5.9374 |
| CPILFESL | month_end | 52 | 0.9038 | 2.5929 | 5.9447 |
| CPILFESL | month_open | 50 | 0.8800 | 2.7379 | 6.2343 |
| CPILFESL | pre_release | 52 | 0.8846 | 2.5579 | 5.9636 |
| PCEPI | mid_month | 50 | 0.8200 | 3.4199 | 9.7211 |
| PCEPI | month_end | 52 | 0.8269 | 3.3572 | 9.9984 |
| PCEPI | month_open | 49 | 0.8163 | 3.5334 | 9.5745 |
| PCEPI | pre_release | 52 | 0.8269 | 3.3198 | 9.7935 |
| PCEPILFE | mid_month | 50 | 0.8400 | 2.4373 | 6.0801 |
| PCEPILFE | month_end | 52 | 0.8462 | 2.2097 | 6.2203 |
| PCEPILFE | month_open | 49 | 0.8163 | 2.5239 | 6.1891 |
| PCEPILFE | pre_release | 52 | 0.8462 | 2.1272 | 6.0762 |

## Governance conclusion

The stable target-stage map is the Model 1B point-forecast candidate. The adaptive selector remains shadow-only because its gains are concentrated in a minority of target-stage groups and it worsens several headline and core-inflation comparisons on the same eligible months. The exponentially weighted empirical 80% quantile is the interval candidate because it has the lowest predeclared interval score and acceptable aggregate and stage-level coverage. This validation is not a production freeze: live governance, news decomposition, and a governed candidate forecast are still required.