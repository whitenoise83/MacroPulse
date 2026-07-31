# Model 1B — US Inflation Nowcast: Draft Model Card

## Status

- Model ID: `US_INFLATION_NOWCAST_1B`
- Version: `0.5.0`
- Lifecycle: development
- Production use: prohibited

## Targets

- Headline CPI (`CPIAUCSL`)
- Core CPI (`CPILFESL`)
- Headline PCE price index (`PCEPI`)
- Core PCE price index (`PCEPILFE`)

Forecasts are monthly log changes annualised by multiplying by 1,200.

## Current models

- AR(1)
- Trailing 12-month mean
- Bridge Ridge
- Equal-weight Ridge-AR ensemble

## Vintage validation

v0.2 reconstructs historical ALFRED information sets at four predeclared stages:
month open, mid-month, month end, and one day before the initial target release.
The realised outcome is calculated from the target index snapshot available on
its initial release date.

## Controls

- Forecast cutoffs must precede target release dates.
- Target-month index observations are prohibited before release.
- Observation dates may not exceed the information cutoff.
- Every forecast stores a 64-character information-set hash.
- All declared models must be present for each evaluated information set.

## Known limitations

- Model specifications remain baseline research models.
- Current predictors use conservative lag structures and do not yet exploit
  partial within-month high-frequency data fully.
- Prior-only intervals exist, but the final production calibration method is not yet selected.
- A stable target-stage policy candidate exists, but it has not been production-approved.
- Inflation news decomposition is not yet implemented.

## v0.3 interval calibration

Model 1B v0.3 replaces development in-sample residual intervals in formal
validation with a separate prior-only calibration layer. For each target,
release stage, and model, the interval half-width is estimated from the finite-
sample-adjusted empirical quantile of absolute pseudo-real-time forecast errors
from strictly earlier target months. The current forecast error is appended only
after that month's interval has been formed. A 24-error warm-up and a 48-month
rolling window are used by default.

## v0.4 stable policy and shadow challenger

Model 1B v0.4 declares a development-stage stable point-forecast policy
candidate. It is not a production approval. The fixed map is intentionally
simple: headline CPI uses the Ridge-AR ensemble at all stages; core CPI uses the
12-month mean at month open and the Ridge-AR ensemble thereafter; headline PCE
uses Bridge Ridge at all stages; core PCE uses Bridge Ridge at month open and the
Ridge-AR ensemble thereafter.

A prior-only shadow selector is evaluated separately. It requires at least 24
previous forecast errors, uses a 36-month rolling window, and applies a 2%
switch hurdle plus MAE, upper-tail, and maximum-error guards. The selector cannot
use the current target month's outcome when choosing its current component.

The release also evaluates four predeclared prior-only interval methods on the
stable-policy rows using coverage, average width, and interval score. The
interval tournament is diagnostic and does not itself promote an interval
method to production.


## v0.4.1 verification additions

- Fixed and adaptive policies are compared only on identical target/stage/month keys after the shadow warm-up.
- Shadow switching frequency and stable-policy share are reported.
- `exp_weighted_q80` is the interval development candidate because it achieved the lowest mean interval score and narrowest average half-width in the predeclared tournament.
- Neither the adaptive shadow nor the interval candidate is approved for production.


## v0.5 candidate validation

Model 1B v0.5 retains the stable target-stage map as the point-forecast
candidate. The adaptive selector remains shadow-only. On identical eligible
months it improves RMSE, MAE, and p90 absolute error simultaneously in only
four of sixteen target-stage groups and materially worsens several headline
CPI, core-CPI month-open, and core-PCE comparisons.

The selected uncertainty method is `exp_weighted_q80`: an exponentially
weighted empirical 80th percentile of strictly prior absolute forecast errors.
It achieved aggregate coverage of 84.7%, target-stage coverage from 81.6% to
90.4%, the lowest mean interval score, and the narrowest average half-width in
the predeclared tournament.

The candidate validation repeats no-look-ahead, target-leakage, release timing,
hash, sample-size, relative-accuracy, bias, challenger-stability, and interval
quality gates. A pass is a candidate milestone, not production approval. Live
news decomposition, governed live forecast registration, freeze assessment, and
model-owner signoff remain outstanding.
