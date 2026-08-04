# Model 1D v0.3.7

## Top-two miss attribution and rolling-frequency robustness audit

This overlay consumes the frozen Model 1D v0.3.6 evidence. It does not re-estimate, retune, recalibrate, or otherwise change the source model.

It attributes every source top-two miss, separates narrow rank-three misses from deep misses, distinguishes transition and stable-state performance, attributes misses to dimensions where evidence permits, and compares the source directly with `rolling_frequency` using paired loss differences and circular block bootstrap intervals.

## Governance boundary

The retrospective audit sample was already consumed. Therefore v0.3.7 has no promotion authority, even when its diagnostic architecture passes.

Permitted conclusions are:

- source advantage over rolling frequency appears robust;
- source advantage is statistically inconclusive;
- rolling frequency is not materially inferior.

## Installation

Extract the ZIP into the MacroPulse repository root, then run:

```cmd
python scripts\apply_model1d_v0_3_7_overlay.py
pip install -e .
python scripts\initialise_database.py
python -m pytest -q tests\test_macro_state_top2_robustness.py tests\test_macro_state_top2_robustness_pipeline.py
python scripts\run_macro_state_top2_robustness.py
```

The patcher updates the existing governance file, package source list, and Streamlit page. It creates `.v036.bak` safety copies; do not commit those backups.

## Evidence limitation: dimension attribution

The frozen v0.3.6 benchmark-prediction file does not contain monthly growth,
inflation, or labour scores. The only located score file contains three
aggregate comparisons between target-vintage modes and has no date fields.
It cannot be joined causally to the 42 fold-month observations.

Accordingly, v0.3.7 records dimension and adjacency attribution as
`unavailable_from_frozen_v036_evidence`. It does not substitute latest-revised
or unrelated score evidence.

## Metric reconciliation

Soft log loss uses the same `1e-12` probability floor as v0.3.6. Governance
requires source and rolling-frequency Brier score, log loss, and top-two
coverage to reconcile with the committed v0.3.6 summaries.
