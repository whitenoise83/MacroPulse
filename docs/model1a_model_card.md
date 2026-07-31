# MacroPulse Model 1A - US GDP Nowcast Model Card

## Status

- Model ID: `US_GDP_NOWCAST_1A`
- Production version: `1.0.0`
- Lifecycle: `production`
- Approved: 29 July 2026
- Approved validation ID: `7ee34d06-f393-4fb7-90ef-6239758f8503`
- Validation result: 27 passed, 0 failed, 0 warnings
- Target: annualised quarter-on-quarter US real GDP growth
- Evaluation outcome: initial GDPC1 release

## Intended use

Estimate current-quarter US real GDP growth from the information available at a
specified historical or live cutoff. The model is intended for macroeconomic
research, scenario preparation, and release interpretation. It is not a promise
of investment performance.

## Approved production policy

The **Stable Stage Policy** publishes a predeclared component at each stage:

| Forecast stage | Production component |
|---|---|
| `early_quarter` | Dynamic Factor Model |
| `after_month_1` | Dynamic Factor Model |
| `after_month_2` | fixed Bridge-DFM Ensemble |
| `quarter_end` | Rolling Bridge-DFM Ensemble |
| `pre_advance_release` | Dynamic Factor Model |

If the DFM is unavailable or required inputs are materially stale, Bridge Ridge
is the operational fallback.

## Shadow challenger

The **Robust Stage-Adaptive Policy** remains shadow-only. It uses only earlier
completed same-stage outcomes and compares Bridge Ridge, DFM, fixed Bridge-DFM,
and rolling Bridge-DFM on a common trailing sample.

- minimum history: 20 common quarters;
- trailing window: 20 quarters;
- switching hurdle: at least 5% composite-score improvement;
- score: 40% RMSE, 25% MAE, 20% trimmed RMSE, 15% p90 absolute error;
- tail guard: p90 error no more than 10% above the incumbent;
- maximum-error guard: no more than 25% above the incumbent.

The shadow policy cannot replace production without a separately versioned and
validated governance decision.

## Uncertainty

The target interval is 80%. Once at least 12 earlier stage/model errors exist,
the interval half-width is the rolling empirical absolute-error quantile over up
to 20 completed quarters. Validation reports stage-level exact-binomial tests,
a target-quarter clustered bootstrap for pooled coverage, average and median
width, and Winkler interval score.

## Inputs

- Real GDP
- Industrial production
- Nonfarm payrolls
- Advance retail sales
- Housing starts
- Manufacturing weekly hours
- Unemployment rate
- CPI
- Effective federal funds rate

See `docs/model1a_data_dictionary.md` and
`docs/model1a_transformation_dictionary.md`.

## Validation evidence

- FRED/ALFRED pseudo-real-time snapshots
- Five within-quarter forecast stages
- 45 evaluated quarters per stage
- No future observations or revisions
- Initial GDP release as the outcome
- Prior-only rolling weights and interval calibration
- Stage comparisons against eligible static candidates
- Regime reporting for pre-pandemic, pandemic, post-pandemic, and recent periods
- DFM failure rate of zero in the approved staged validation
- Exact news-decomposition arithmetic and immaterial residual

## Principal limitations

- Pandemic annualised GDP movements dominate untrimmed RMSE.
- The stable stage map was selected on the development sample.
- The initial indicator set is intentionally small.
- Retail sales are nominal in the current registry.
- Release timing is represented by declared cutoffs rather than intraday timestamps.
- The DFM is a one-factor specification.
- Historical relationships may change after structural breaks.
- Model 1A covers GDP only; inflation and labour nowcasts are future branches.
