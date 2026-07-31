# MacroPulse Model 1B v0.4 Policy Evaluation

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

## Prior-only shadow performance

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

## Interval-method tournament

| interval_method | observations | coverage | average_half_width | mean_interval_score | median_interval_score |
|---|---|---|---|---|---|
| exp_weighted_q80 | 818 | 0.8472 | 3.2605 | 9.1037 | 6.5547 |
| target_shrunk_q80 | 818 | 0.8704 | 3.3538 | 9.2186 | 6.8860 |
| rolling_q80 | 818 | 0.8704 | 3.3688 | 9.2246 | 6.8791 |
| ewma_gaussian | 818 | 0.8729 | 3.4031 | 9.3257 | 6.9056 |

## Governance interpretation

The fixed map was chosen for stability using the completed vintage evidence. The shadow selector uses only earlier forecast errors and remains non-production. The interval tournament is diagnostic; a method must not be promoted solely because it wins on the same evaluation sample.