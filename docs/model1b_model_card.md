# MacroPulse Model 1B — US Inflation Nowcast Model Card

## Status

- Model ID: `US_INFLATION_NOWCAST_1B`
- Version: `1.0.0`
- Lifecycle: production
- Model owner: MacroPulse
- Owner approval: `APPROVE MODEL 1B FREEZE`
- Approval date: `2026-07-31T11:12:00+01:00`

## Purpose and targets

Model 1B produces monthly nowcasts for:

- Headline CPI (`CPIAUCSL`)
- Core CPI (`CPILFESL`)
- Headline PCE price index (`PCEPI`)
- Core PCE price index (`PCEPILFE`)

Forecasts are monthly log changes annualised by multiplying by 1,200.

## Forecast stages

- Month open
- Mid-month
- Month end
- One day before the estimated initial release

## Approved point policy

| Target | Month open | Mid-month | Month end | Pre-release |
|---|---|---|---|---|
| Headline CPI | Ridge-AR Ensemble | Ridge-AR Ensemble | Ridge-AR Ensemble | Ridge-AR Ensemble |
| Core CPI | 12-Month Mean | Ridge-AR Ensemble | Ridge-AR Ensemble | Ridge-AR Ensemble |
| Headline PCE | Bridge Ridge | Bridge Ridge | Bridge Ridge | Bridge Ridge |
| Core PCE | Bridge Ridge | Ridge-AR Ensemble | Ridge-AR Ensemble | Ridge-AR Ensemble |

The adaptive prior-only selector remains a separately persisted shadow
challenger and cannot control a production headline.

## Uncertainty

The approved interval method is `exp_weighted_q80`, an exponentially weighted
empirical 80th percentile of strictly prior absolute pseudo-real-time errors for
the same target, stage, and selected model.

- Nominal coverage: 80%
- Minimum prior errors: 24
- Rolling window: 48 months
- Half-life: 18 months

In the predeclared interval tournament it achieved aggregate coverage of 84.7%,
target-stage coverage from 81.6% to 90.4%, the lowest mean interval score, and
the narrowest average half-width among the tested candidates.

## Validation evidence

- Vintage backtest ID: `fdd2f573-a425-4abc-8056-f9843955bac2`
- Candidate validation: `5f0cd6ea-c41f-44da-a21a-43490d8e75ce` — 28 passed, 0 failed, 0 warnings
- Operational validation: `58c89931-0f6b-43ed-8815-abbc99fa4ac8` — 20 passed, 0 failed, 0 warnings
- Freeze assessment: `2b7fe987-384a-451b-971f-03d5bf5106c7` — 14 passed, 0 failed, 0 warnings
- Governed live run: `905deade-2bbf-4c89-801e-ce296bb00d97`

## Controls

- Historical information sets are reconstructed from ALFRED vintages.
- Forecast cutoffs precede target releases.
- Unreleased target-month indexes are excluded.
- Observation dates cannot exceed the information cutoff.
- Interval calibration and shadow selection use prior outcomes only.
- Every live run stores configuration, code, information-set, model-state, and governance hashes.
- News decomposition attributes revisions, removed observations, new observations, refit, and policy effects and checks arithmetic reconciliation.

## Known limitations

- Annualised monthly rates can appear volatile and should not be interpreted as year-over-year inflation.
- The predictor set uses conservative lag structures and may not fully exploit all high-frequency within-month information.
- News attribution is path-dependent and should be interpreted using the disclosed attribution order.
- The stable policy was selected using a finite historical sample that includes unusual pandemic and post-pandemic inflation dynamics.
- Production monitoring is required; historical validation does not guarantee future accuracy.

## Change control

Any material target, predictor, transformation, release-stage, data-source,
model-policy, or uncertainty-method change requires a new version, documented
challenger evidence, revalidation, and explicit owner approval.
