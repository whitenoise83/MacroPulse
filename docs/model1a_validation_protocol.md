# Model 1A Validation Protocol

## 1. Data-vintage integrity

For every forecast cutoff, confirm that observations and revisions come from the
historical information set available on that date. Target-quarter GDP must be
absent, and its initial release must occur after the forecast cutoff.

## 2. Production and shadow decisions

The Stable Stage Policy must follow the predeclared component map. Rolling
ensemble weights, interval calibration, and Robust Stage-Adaptive Policy
selection must use only earlier completed target quarters from the same forecast
stage. Candidate models must be compared on a common historical sample.

## 3. Benchmark evaluation

Compare Bridge Ridge, DFM, fixed Bridge-DFM, rolling Bridge-DFM, Stable Stage
Policy, Robust Stage-Adaptive Policy, and AR(1) using:

- RMSE and 10% trimmed RMSE;
- MAE, median absolute error, p90 absolute error, maximum error, and bias;
- direction accuracy and skill over the always-positive benchmark;
- interval coverage, width, and Winkler interval score;
- quarter-level win rates.

## 4. Production competitiveness gates

At every forecast stage, compare the Stable Stage Policy with the best eligible
static candidate on the same sample. Require:

- RMSE ratio no greater than 1.10;
- MAE ratio no greater than 1.10;
- p90 absolute-error ratio no greater than 1.20;
- maximum-error ratio no greater than 1.25.

## 5. Interval validation

For the 80% interval, report:

- stage-level observed coverage and exact-binomial p-values;
- target-quarter clustered-bootstrap pooled coverage;
- average and median interval width;
- Winkler interval score;
- raw versus calibrated interval results.

The clustered test is required because five stage forecasts for one quarter
share the same realised GDP outcome.

## 6. Selection stability

For the robust shadow policy, report model switches, switch rate, average and
minimum model duration, and reasons for retained incumbents or switches.

## 7. Regime evaluation

Review full-sample, pre-pandemic, pandemic, post-pandemic, and last-20-quarter
results. Preserve crisis observations in the main statistics and use trimmed and
median metrics only as complementary evidence.

## 8. Operational evaluation

Confirm that API failures, stale data, missing observations, DFM non-convergence,
model switches, and news-decomposition failures are visible and cannot silently
produce an apparently governed forecast.

## 9. Reproducibility

Every live forecast must store model version, configuration hash, code hash, Git
commit where available, information-set hash, cutoff, target period, forecast
stage, production component, effective production weights, robust shadow choice,
and interval.

## 10. Production governance

Model 1A v1.0.0 was promoted after the automated validation report, freeze
assessment, model card, dictionaries, runbook, known limitations, and explicit
model-owner sign-off were completed. Future changes require a new version,
challenger evidence, full revalidation, and a recorded approval decision.

### Coherent upper-tail comparator

The production p90 absolute error is compared only with static models that are
also accuracy-competitive under the declared RMSE, MAE, and maximum-error gates.
A model cannot become the tail benchmark solely by reducing p90 while producing
materially worse average or crisis-period errors. The p90 ratio limit remains 1.20.
