# MacroPulse Model 1D v0.3.6

## Fixed-Horizon Target Lock and Probabilistic Benchmark Audit

Model 1D v0.3.6 locks the fixed-90-day five-family target and tests whether the frozen source probabilities add value over properly constructed causal probabilistic benchmarks.

This is a research audit. It is not a production promotion package.

## Run

```cmd
python scripts\run_macro_state_fixed_horizon_probabilistic.py
```

## Outputs

Evidence is written to:

```text
reports\macro_state_fixed_horizon_probabilistic\
```

The report set contains target-lock metadata, state availability, missing evidence, benchmark predictions, rolling metrics, calibration reliability, fold comparisons, bootstrap results, prospective-shadow status, and governance checks.

## Governance reference

The pre-specified governance reference is `soft_persistence`. Other probabilistic benchmarks are reported to prevent a favourable comparison from depending on an artificially overconfident one-hot baseline.

## Status

`US_MACRO_STATE_1D v0.3.6 development`

## Realised audit result

Governance result: FAIL

The frozen Model 1D source passed all fixed-horizon probabilistic audit gates except source top-two coverage. Observed top-two coverage was 0.5714285714 against the required threshold of 0.65.

The source ranked first by mean soft Brier score, beat the pre-specified soft-persistence reference in all seven folds, and achieved a strictly positive bootstrap lower margin. Failure of the predeclared top-two coverage gate prevents promotion.

Status: fixed-horizon probabilistic research evidence only. Model 1D remains development-stage and is not candidate or production approved.
