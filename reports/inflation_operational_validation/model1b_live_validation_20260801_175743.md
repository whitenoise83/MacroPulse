# MacroPulse Model 1B v1.0.0 Governed Live Validation

- Validation ID: `df59c366-563a-42d8-9b29-8d87bce1e9ce`
- Live run ID: `be5ba1a0-6667-4c7b-bbd9-32f8e5d8def4`
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
| Reproducibility | Stored information-set hash reproduces from persisted observations | pass | bf1c56454341f4e3d48d89b2c1664fb7b90af2e5d0ed32d113fa800ffa556e32 | bf1c56454341f4e3d48d89b2c1664fb7b90af2e5d0ed32d113fa800ffa556e32 |
| Reproducibility | Stored model-state hash reproduces from components and coefficients | pass | 40a9c31d8c92e3fccd05b3eaec6a58f09d9404af68f3d86d31738e5595e4439d | 40a9c31d8c92e3fccd05b3eaec6a58f09d9404af68f3d86d31738e5595e4439d |
| Governance | Governance signature reproduces from the persisted live payload | pass | 7aa803ac464cde16f0a9ccd7bdeaae30527f046ae28434eb6ece7eaffddbdf8a | 7aa803ac464cde16f0a9ccd7bdeaae30527f046ae28434eb6ece7eaffddbdf8a |
| Econometric validity | No persisted observation is dated after the live information cutoff | pass | 0 | 0 future-dated observations |
| Econometric validity | Unreleased target-month indexes are absent from the live information set | pass | 0 | 0 leaked targets |
| Governance | Live run stores a candidate-validation reference | pass | 5f0cd6ea-c41f-44da-a21a-43490d8e75ce | valid candidate validation ID |
| Operational reliability | Every governed headline has a news-decomposition status | pass | 4 | 4 targets |
| Operational reliability | Comparable inflation news decompositions reconcile arithmetically | pass | 0.0 | <= 1e-08 |
| Governance | Referenced candidate validation exists and passed without warnings | pass | pass / 28 passed | pass with 0 failures and 0 warnings |

The run is a production-governed live forecast. A passing operational validation demonstrates reproducibility, stable-policy control, prior-only intervals, shadow separation, and news reconciliation.