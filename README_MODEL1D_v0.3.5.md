# MacroPulse Model 1D v0.3.5

## Real-Time Target Reconstruction and Soft Five-Family Audit

Model 1D v0.3.5 does not reopen the specification tournament. It keeps the
v0.3.1 research source fixed and addresses the main weaknesses identified by
v0.3.4: unspecified realised-data vintages, fragile hard labels, and failure to
beat persistence.

The release reconstructs three locally available target modes:

- `initial_release`: outcomes stored by the approved pseudo-real-time source
  backtests together with their initial release dates;
- `fixed_horizon_90d`: the latest cached historical snapshot no later than
  target-period end plus 90 days;
- `latest_revised`: the latest locally stored observation vintage.

No web or FRED request is made by the audit.

## Soft-target architecture

The five-family state becomes the primary research target:

- `contraction`
- `adverse_supply`
- `inflationary_expansion`
- `benign_expansion`
- `mixed`

The eight-state regime remains a secondary subtype.

For each realised month, the audit combines:

- the pre-specified `sensitive`, `baseline`, and `conservative` threshold sets;
- a deterministic ±0.10 perturbation grid over growth, inflation, and labour
  scores.

The resulting family frequencies form a soft target distribution. Each month
records the primary family, secondary subtype, top probability, probability
margin, ambiguity flag, and plausible alternative families.

## Forecast evaluation

The frozen source family probabilities are compared with lagged-target
persistence across the existing seven rolling-origin folds using:

- family accuracy, balanced accuracy, and macro-F1;
- confidence-weighted accuracy;
- soft-label Brier score and cross-entropy loss;
- top-two coverage;
- rolling-fold persistence win rate;
- block-bootstrap confidence bounds for the monthly source margin.

The 2024-08 to 2026-03 audit remains consumed and receives no selection weight.
Months from 2026-04 onward are reserved as prospective shadow evidence.

## Outputs

The audit writes Markdown, JSON, and CSV evidence under:

`reports/macro_state_realtime_targets/`

No new DuckDB tables are introduced.

## Run

```cmd
python scripts\run_macro_state_realtime_soft_targets.py
```

## Governance

A passing audit would still not constitute production approval. Model 1D must
remain research-only unless actual-vintage coverage is adequate, the soft
five-family target is stable across revisions, and the source beats persistence
with a strictly positive bootstrap lower margin.
