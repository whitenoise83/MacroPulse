# Model 1D v0.3.5 — Real-Time Targets and Soft Labels

## Purpose

v0.3.4 showed that the eight-state target was economically descriptive but
failed target-validity governance. The most important failures were missing
revision-vintage attribution, sensitivity to thresholds and small score
perturbations, and zero rolling-fold dominance over naive benchmarks.

v0.3.5 changes the evaluation architecture rather than searching more model
parameters.

## Frozen forecast source

The source remains the v0.3.1 rolling-origin research leader:

- normalisation: `expanding_robust_z`
- inflation weights: `policy`
- labour weights: `equal`
- thresholds: `sensitive`
- uncertainty: `independent_normal`

Its prior promotion failure remains binding.

## Actual-vintage reconstruction

### Initial release

The approved GDP, inflation, and labour pseudo-real-time backtests store the
actual value and initial release date used for validation. v0.3.5 treats those
records as the initial-release target.

### Fixed 90-day horizon

For each target period, the audit requests target-period end plus 90 days and
selects the latest cached historical snapshot no later than that date and no
more than 45 days stale. The source-series transform is then reapplied to the
snapshot. When suitable cached evidence is absent, the target remains missing.

### Latest revised

The audit transforms the latest locally stored observations for each source
series. It does not contact FRED or ALFRED.

## Soft family labels

For each target mode and month, the realised growth, inflation, and labour
scores are classified under three pre-specified threshold systems and all 27
corners of a ±0.10 score perturbation cube. The 81 scenario classifications are
converted into:

- a five-family probability vector;
- an eight-state probability vector;
- a primary family and secondary subtype;
- a top probability and probability margin;
- an ambiguity indicator;
- alternative plausible families.

This prevents a month sitting close to a boundary from carrying the same
validation weight as a month deep inside a regime.

## Forecast probabilities

The source eight-regime probabilities are aggregated into five families. When
probabilities are unavailable, the source point family is represented as a
one-hot distribution.

Lagged-target persistence uses the previous contiguous month's realised soft
family distribution.

## Metrics

The rolling evaluation reports:

- family accuracy;
- family balanced accuracy;
- family macro-F1;
- confidence-weighted accuracy;
- soft Brier score;
- soft cross-entropy loss;
- top-two family coverage;
- probability assigned to the primary realised family;
- source-versus-persistence fold margins;
- a block-bootstrap confidence interval for monthly weighted margins.

## Prospective shadow

Months beginning 2026-04-30 are reserved as prospective shadow evidence. They
must not enter historical selection or the already consumed 2024-08 to 2026-03
audit.

## Promotion rule

v0.3.5 is diagnostic research evidence only. Model 1D cannot return to candidate
selection unless:

- initial-release and revised targets are sufficiently complete;
- fixed-horizon cached-vintage coverage is adequate;
- initial and revised family labels agree sufficiently often;
- ambiguity remains below the governance ceiling;
- the source beats persistence in most rolling folds;
- the block-bootstrap lower margin is strictly positive;
- prospective shadow isolation remains intact.
