# MacroPulse Model 1B v1.0.0 Governed Live Validation

- Validation ID: `25d89ee4-730d-44e1-bfa1-c6120e49ec00`
- Live run ID: `905deade-2bbf-4c89-801e-ce296bb00d97`
- Status: **PASS**

| Gate | Check | Status | Observed | Threshold |
|---|---|---:|---:|---:|
| Operational reliability | Governed live run completed successfully | pass | success | success |
| Data integrity | Exactly one governed headline exists for each inflation target | pass | 4 targets; 0 duplicates | 4 targets and 0 duplicates |
| Policy governance | Every live forecast uses a declared release stage | pass | 0 | 0 invalid stages |
| Policy governance | Stable live policy follows the validated target-stage map | pass | 0 | 0 violations |
| Reproducibility | Every headline matches its stored model component | pass | 0 | 0 mismatches |
| Challenger governance | Adaptive forecasts are stored separately as shadow outputs | pass | 0 | 0 missing shadow outputs |
| Uncertainty calibration | Every live interval uses the validated candidate method | pass | 0 | 0 methods other than exp_weighted_q80 |
| Uncertainty calibration | Every live interval has a finite positive half-width | pass | 0 | 0 invalid widths |
| Uncertainty calibration | Every live interval has sufficient strictly prior error history | pass | 48 | >= 24 |
| Econometric validity | Live interval calibration uses only earlier target months | pass | 0 | 0 violations |
| Reproducibility | Governed run contains complete SHA-256 provenance hashes | pass | 0 | 0 invalid hashes |
| Reproducibility | Stored information-set hash reproduces from persisted observations | pass | d9858844210379c5bae695fcc825b297f8b9f565871730fdb24473fb61b5dc22 | d9858844210379c5bae695fcc825b297f8b9f565871730fdb24473fb61b5dc22 |
| Reproducibility | Stored model-state hash reproduces from components and coefficients | pass | 9bd51867091289a0cb3767ed8579ecd7c4c095ede9121b9680fa397484d7909e | 9bd51867091289a0cb3767ed8579ecd7c4c095ede9121b9680fa397484d7909e |
| Governance | Governance signature reproduces from the persisted live payload | pass | 7ed59fca8124bf1adb4bf1a97d39c175632c2661a8fc0e56b3ac64f317389a34 | 7ed59fca8124bf1adb4bf1a97d39c175632c2661a8fc0e56b3ac64f317389a34 |
| Econometric validity | No persisted observation is dated after the live information cutoff | pass | 0 | 0 future-dated observations |
| Econometric validity | Unreleased target-month indexes are absent from the live information set | pass | 0 | 0 leaked targets |
| Governance | Live run stores a candidate-validation reference | pass | 5f0cd6ea-c41f-44da-a21a-43490d8e75ce | valid candidate validation ID |
| Operational reliability | Every governed headline has a news-decomposition status | pass | 4 | 4 targets |
| Operational reliability | Comparable inflation news decompositions reconcile arithmetically | pass | 0.0 | <= 1e-08 |
| Governance | Referenced candidate validation exists and passed without warnings | pass | pass / 28 passed | pass with 0 failures and 0 warnings |

The run is a production-governed live forecast. A passing operational validation demonstrates reproducibility, stable-policy control, prior-only intervals, shadow separation, and news reconciliation.