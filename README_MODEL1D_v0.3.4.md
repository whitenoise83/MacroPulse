# MacroPulse Model 1D v0.3.4

## Target-Definition and Benchmark-Validity Audit

Model 1D v0.3.4 does not reopen the specification tournament. It keeps the
v0.3.1 research source fixed and audits whether the realised macro-regime label
is a valid, stable, real-time-consistent, economically useful forecasting target.

The release evaluates four questions:

1. Are the forecast inputs historically causal, and are the realised targets
   explicitly tied to a real-time revision vintage?
2. Are the eight-state and five-family labels stable under small score
   perturbations and alternative pre-specified threshold sets?
3. Does the source classifier beat persistence, training mode, rolling mode,
   a first-order Markov benchmark, and a simple sign-rule benchmark?
4. Do the eight-state labels separate subsequent growth, inflation, and labour
   outcomes more strongly than the five-family labels?

## Frozen source

- Normalisation: `expanding_robust_z`
- Inflation weights: `policy`
- Labour weights: `equal`
- Thresholds: `sensitive`
- Uncertainty: `independent_normal`

The source candidate remains research-only and failed its v0.3.1 promotion gate.

## Outputs

The audit writes Markdown, JSON, and CSV evidence under:

`reports/macro_state_target_validity/`

No new DuckDB tables are introduced.

## Run

```cmd
python scripts\run_macro_state_target_validity_audit.py
```

## Governance

A passing audit is not a production approval. A failing audit prevents another
candidate-selection tournament until the target-definition weaknesses are
resolved. The 2024-08 to 2026-03 audit period remains consumed and report-only.
