# MacroPulse Model 1B v0.4.1 Common-Sample Policy Verification

- Backtest ID: `fdd2f573-a425-4abc-8056-f9843955bac2`
- Status: **development research**
- Fixed policy is a production candidate, not an approved production policy.

## Stable candidate policy

| Target | Stage | Component |
|---|---|---|
| CPIAUCSL | month_open | Inflation Ridge-AR Ensemble |
| CPIAUCSL | mid_month | Inflation Ridge-AR Ensemble |
| CPIAUCSL | month_end | Inflation Ridge-AR Ensemble |
| CPIAUCSL | pre_release | Inflation Ridge-AR Ensemble |
| CPILFESL | month_open | Inflation 12-Month Mean |
| CPILFESL | mid_month | Inflation Ridge-AR Ensemble |
| CPILFESL | month_end | Inflation Ridge-AR Ensemble |
| CPILFESL | pre_release | Inflation Ridge-AR Ensemble |
| PCEPI | month_open | Inflation Bridge Ridge |
| PCEPI | mid_month | Inflation Bridge Ridge |
| PCEPI | month_end | Inflation Bridge Ridge |
| PCEPI | pre_release | Inflation Bridge Ridge |
| PCEPILFE | month_open | Inflation Bridge Ridge |
| PCEPILFE | mid_month | Inflation Ridge-AR Ensemble |
| PCEPILFE | month_end | Inflation Ridge-AR Ensemble |
| PCEPILFE | pre_release | Inflation Ridge-AR Ensemble |

## Fixed-policy performance

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

## Prior-only shadow performance (raw eligible sample)

| target_series | forecast_stage | observations | rmse | mae | bias | median_ae | p90_abs_error | max_abs_error | model_name |
|---|---|---|---|---|---|---|---|---|---|
| CPIAUCSL | mid_month | 52 | 3.9140 | 2.6043 | -0.2032 | 1.3215 | 6.8381 | 12.7183 | Adaptive shadow |
| CPIAUCSL | month_end | 52 | 3.9210 | 2.5957 | -0.2120 | 1.2747 | 6.8381 | 12.7183 | Adaptive shadow |
| CPIAUCSL | month_open | 50 | 4.0507 | 2.8336 | -0.2809 | 2.0735 | 6.4411 | 12.4333 | Adaptive shadow |
| CPIAUCSL | pre_release | 52 | 3.9200 | 2.6095 | -0.2240 | 1.2747 | 6.8629 | 12.7956 | Adaptive shadow |
| CPILFESL | mid_month | 52 | 1.5334 | 1.2084 | 0.1896 | 1.0478 | 2.6069 | 3.7891 | Adaptive shadow |
| CPILFESL | month_end | 52 | 1.5354 | 1.2056 | 0.1867 | 0.9973 | 2.6069 | 3.7891 | Adaptive shadow |
| CPILFESL | month_open | 50 | 1.8438 | 1.3787 | -0.2385 | 0.9878 | 3.2035 | 4.7073 | Adaptive shadow |
| CPILFESL | pre_release | 52 | 1.5285 | 1.2089 | 0.1883 | 1.0638 | 2.6071 | 3.7779 | Adaptive shadow |
| PCEPI | mid_month | 50 | 2.5443 | 1.8923 | -0.1712 | 1.3055 | 4.3944 | 7.0609 | Adaptive shadow |
| PCEPI | month_end | 52 | 2.6284 | 1.9029 | 0.0340 | 1.3786 | 4.7138 | 8.4291 | Adaptive shadow |
| PCEPI | month_open | 49 | 2.6305 | 1.9217 | -0.1543 | 1.4142 | 4.6423 | 7.4308 | Adaptive shadow |
| PCEPI | pre_release | 52 | 2.5376 | 1.8189 | -0.0689 | 1.2226 | 4.0460 | 8.3838 | Adaptive shadow |
| PCEPILFE | mid_month | 50 | 1.6478 | 1.2818 | -0.1295 | 0.9632 | 2.6277 | 5.0149 | Adaptive shadow |
| PCEPILFE | month_end | 52 | 1.7261 | 1.2850 | -0.0920 | 0.8639 | 2.6870 | 4.8604 | Adaptive shadow |
| PCEPILFE | month_open | 49 | 1.6613 | 1.3271 | -0.3187 | 1.0325 | 2.7460 | 4.0954 | Adaptive shadow |
| PCEPILFE | pre_release | 52 | 1.6972 | 1.2563 | -0.1438 | 0.7597 | 2.6870 | 4.9362 | Adaptive shadow |

## Fixed versus shadow on identical eligible months

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

## Interval-method tournament

| interval_method | observations | coverage | average_half_width | mean_interval_score | median_interval_score |
|---|---|---|---|---|---|
| exp_weighted_q80 | 818 | 0.8472 | 3.2605 | 9.1037 | 6.5547 |
| target_shrunk_q80 | 818 | 0.8704 | 3.3538 | 9.2186 | 6.8860 |
| rolling_q80 | 818 | 0.8704 | 3.3688 | 9.2246 | 6.8791 |
| ewma_gaussian | 818 | 0.8729 | 3.4031 | 9.3257 | 6.9056 |

## Selected interval candidate: exp_weighted_q80

| target_series | forecast_stage | observations | coverage | average_half_width | mean_interval_score | median_interval_score |
|---|---|---|---|---|---|---|
| CPIAUCSL | mid_month | 52 | 0.8269 | 4.5949 | 14.1629 | 8.6642 |
| CPIAUCSL | month_end | 52 | 0.8462 | 4.6205 | 14.1910 | 8.9303 |
| CPIAUCSL | month_open | 50 | 0.8600 | 5.0108 | 15.2327 | 8.8561 |
| CPIAUCSL | pre_release | 52 | 0.8269 | 4.5426 | 14.2318 | 8.7726 |
| CPILFESL | mid_month | 52 | 0.8846 | 2.5764 | 5.9374 | 4.9072 |
| CPILFESL | month_end | 52 | 0.9038 | 2.5929 | 5.9447 | 4.9072 |
| CPILFESL | month_open | 50 | 0.8800 | 2.7379 | 6.2343 | 6.2724 |
| CPILFESL | pre_release | 52 | 0.8846 | 2.5579 | 5.9636 | 4.9386 |
| PCEPI | mid_month | 50 | 0.8200 | 3.4199 | 9.7211 | 7.2243 |
| PCEPI | month_end | 52 | 0.8269 | 3.3572 | 9.9984 | 7.1007 |
| PCEPI | month_open | 49 | 0.8163 | 3.5334 | 9.5745 | 7.4678 |
| PCEPI | pre_release | 52 | 0.8269 | 3.3198 | 9.7935 | 6.9324 |
| PCEPILFE | mid_month | 50 | 0.8400 | 2.4373 | 6.0801 | 5.1675 |
| PCEPILFE | month_end | 52 | 0.8462 | 2.2097 | 6.2203 | 4.6747 |
| PCEPILFE | month_open | 49 | 0.8163 | 2.5239 | 6.1891 | 5.4093 |
| PCEPILFE | pre_release | 52 | 0.8462 | 2.1272 | 6.0762 | 4.6241 |

## Governance interpretation

The fixed map was chosen for stability using the completed vintage evidence. The shadow selector uses only earlier forecast errors and remains non-production. The interval tournament is diagnostic; a method must not be promoted solely because it wins on the same evaluation sample.