# Model 1C — US Labour Market Nowcast Engine (Draft Model Card)

## Purpose

Provide monthly forecasts for nonfarm payroll change, unemployment, and wage
growth as the third pillar of the MacroPulse unified macro state.

## Current version

v0.4.0 development policy candidate.

## Targets

- `PAYEMS`: monthly nonfarm payroll change, thousands of jobs.
- `UNRATE`: unemployment rate, percent.
- `CES0500000003`: monthly average-hourly-earnings growth annualised by 1,200.

## Evidence completed

- Initial-release target outcomes and ALFRED information sets.
- Five predeclared forecast stages.
- No-look-ahead and target-leakage controls.
- Prior-only `exp_weighted_q80` interval calibration.
- Twenty vintage-validation gates passed with no failures or warnings.
- Stable 15-decision point-policy candidate and adaptive shadow tournament.

## Stable candidate policy

- Payrolls: 12-month mean at month open; equal-weight ensemble after week 1;
  Bridge Ridge thereafter.
- Unemployment: equal-weight ensemble at all stages.
- Earnings: Bridge Ridge at month open and after week 1; equal-weight ensemble
  thereafter.

## Governance status

The stable map is a development candidate. The adaptive selector uses only
previous forecast errors and remains shadow-only. Common-sample evidence must
be reviewed before candidate validation.

## Known limitations

- Pandemic observations materially influence payroll and unemployment RMSE.
- October 2025 unemployment is structurally unavailable and explicitly excluded.
- No governed live registry or labour news decomposition exists yet.
- No production freeze or owner approval has been completed.

## Next validation stage

v0.5.0 will formalise candidate-validation gates after the fixed-versus-shadow
common-sample results are reviewed.

## v0.5.0 candidate policy

The stable 15-decision target-stage policy is the point-forecast candidate. The
adaptive selector remains shadow-only because its common-sample gains are concentrated
in unemployment-rate groups while payroll and earnings performance generally worsens.
The candidate uncertainty method is the strictly prior `exp_weighted_q80` calibration.
Production use remains prohibited until governed live forecasts, news decomposition,
operational validation, freeze assessment, and owner approval are complete.


## v0.6.0 governed live candidate

Candidate validation `0540c6ee-2d96-493a-adfe-a76c5c91cf31` passed 39/39 gates. The governed live implementation stores the stable policy headline, prior-only `exp_weighted_q80` intervals, adaptive shadow forecasts, the complete information set, provenance hashes, and a governance signature. Labour news attribution separates new observations, revisions/removals, model refit, and stable-policy stage changes. Production approval remains pending live operational validation, freeze assessment, and model-owner signoff.
