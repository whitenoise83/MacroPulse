# MacroPulse Model 1D v0.3.1

## Rolling-Origin Specification Stability Tournament

Model 1D v0.3.1 replaces the unstable single validation split used by v0.3.0
with an expanding-window rolling-origin tournament.

The v0.3.0 validation winner ranked 34th of 36 candidates on the consumed
holdout. v0.3.1 therefore evaluates whether normalization, weighting,
threshold, and uncertainty choices remain competitive across multiple
chronological folds before any specification can advance.

## Samples

With the current 73-state production-vintage reconstruction:

- selection sample: 2020-02-29 through 2024-07-31, 54 complete states;
- consumed external audit: 2024-08-31 through 2026-03-31, 19 complete states;
- October 2025 remains absent because the approved vintage evidence bundle is
  incomplete.

The audit sample is reported but is never used to rank or select the stability
leader.

## Rolling folds

The default design uses:

- minimum expanding training window: 30 states;
- evaluation window: 6 states;
- step: 3 states;
- rolling folds: 7;
- overlapping evaluation windows, handled with block-bootstrap diagnostics.

## Core tournament

All 81 v0.3 core specifications are evaluated in every fold:

- 3 normalization methods;
- 3 inflation weighting systems;
- 3 labour weighting systems;
- 3 threshold systems.

Core stability outputs include mean and median fold score, rank dispersion,
worst fold rank, leading-third rate, fold win rate, average regret, regime
collapse frequency, and dominance over training-mode and persistence
baselines.

## Uncertainty tournament

The 12 leading stable core specifications are combined with:

- independent normal;
- fixed Gaussian copula;
- expanding residual copula.

The 36 final candidates are evaluated fold by fold. The tournament reports
method win rates and proper-score dominance relative to independent normal.

## Governance gates

A research leader must satisfy all configured gates:

- median fold rank in the leading third;
- no catastrophic bottom-tail fold;
- leading-third rate of at least 60%;
- strongest-naive-baseline dominance in at least 60% of folds;
- uncertainty-method win rate of at least 40%;
- non-independent uncertainty methods must dominate independent normal on
  Brier and log scores in at least 60% of folds;
- regime-collapse fold rate no greater than 40%;
- lower block-bootstrap confidence bound on the accuracy margin must be
  strictly positive.

Passing these gates is research evidence only. It is not Model 1D candidate or
production approval.

## Command

```cmd
python scripts\run_macro_state_stability_tournament.py
```

Reports are written to:

```text
reports\macro_state_stability\
```
