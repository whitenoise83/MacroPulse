# MacroPulse Model 1C v0.6.0 Governed Live Validation

- Validation ID: `f535fdc2-c75c-4da8-a0f8-e3d1b80416f3`
- Live run ID: `56adddf6-2438-43cf-97b0-24e4801ac9a4`
- Status: **PASS**

| Gate | Check | Status | Observed | Threshold |
|---|---|---:|---:|---:|
| Operational reliability | Governed live run completed successfully | pass | success | success |
| Data integrity | Exactly one governed headline exists for each labour target | pass | 3 targets; 0 duplicates | 3 targets and 0 duplicates |
| Policy governance | Every live forecast uses a declared release stage | pass | 0 | 0 invalid stages |
| Policy governance | Stable live policy follows the validated target-stage map | pass | 0 | 0 violations |
| Reproducibility | Every headline matches its stored model component | pass | 0 | 0 mismatches |
| Challenger governance | Adaptive forecasts are stored separately as shadow outputs | pass | 0 | 0 missing shadow outputs |
| Uncertainty calibration | Every live interval uses the validated candidate method | pass | 0 | 0 methods other than exp_weighted_q80 |
| Uncertainty calibration | Every live interval has a finite positive half-width | pass | 0 | 0 invalid widths |
| Uncertainty calibration | Every live interval has sufficient strictly prior error history | pass | 48 | >= 24 |
| Econometric validity | Live interval calibration uses only earlier target months | pass | 0 | 0 violations |
| Reproducibility | Governed run contains complete SHA-256 provenance hashes | pass | 0 | 0 invalid hashes |
| Reproducibility | Stored information-set hash reproduces from persisted observations | pass | e239ca660ccb4edcf76a9b1992f4f3fa4f2004499f70d190bfa4b2bfba5d99ba | e239ca660ccb4edcf76a9b1992f4f3fa4f2004499f70d190bfa4b2bfba5d99ba |
| Reproducibility | Stored model-state hash reproduces from components and coefficients | pass | 16517e61fca43334ae961a13b620b0a760fdeffa0c934dd6db5cbbcedd5f9654 | 16517e61fca43334ae961a13b620b0a760fdeffa0c934dd6db5cbbcedd5f9654 |
| Governance | Governance signature reproduces from the persisted live payload | pass | f3f456233660c647e0dcff9db0c62b4f54a3cdbd1aa32ab178737f37313e68de | f3f456233660c647e0dcff9db0c62b4f54a3cdbd1aa32ab178737f37313e68de |
| Econometric validity | No persisted observation is dated after the live information cutoff | pass | 0 | 0 future-dated observations |
| Econometric validity | Unreleased target-month outcomes are absent from the live information set | pass | 0 | 0 leaked targets |
| Governance | Live run stores a candidate-validation reference | pass | 0540c6ee-2d96-493a-adfe-a76c5c91cf31 | valid candidate validation ID |
| Operational reliability | Every governed headline has a news-decomposition status | pass | 3 | 3 targets |
| Operational reliability | Comparable labour news decompositions reconcile arithmetically | pass | 0.0 | <= 1e-08 |
| Governance | Referenced candidate validation exists and passed without warnings | pass | pass / 39 passed | pass with 0 failures and 0 warnings |

The run is a governed live candidate, not a production approval. A passing operational validation demonstrates reproducibility, stable-policy control, prior-only intervals, shadow separation, and news reconciliation.