# MacroPulse Model 1C Freeze Assessment

- Assessment ID: `7eb22dae-54c8-423e-ad1e-9977db08d388`
- Readiness: **ready_for_model_owner_signoff**
- Candidate validation ID: `0540c6ee-2d96-493a-adfe-a76c5c91cf31`
- Operational validation ID: `f535fdc2-c75c-4da8-a0f8-e3d1b80416f3`
- Governed live run ID: `56adddf6-2438-43cf-97b0-24e4801ac9a4`
- Vintage backtest ID: `834e0655-ba81-4b96-b42c-e1cdda73b847`
- Governed live model version: `0.6.0`
- Stable policy decisions: `15`
- Interval method: `exp_weighted_q80`
- Adaptive selector: `shadow challenger only`

## Freeze checks

| Gate | Check | Status | Observed | Threshold |
|---|---|---:|---:|---:|
| Candidate evidence | Passing Model 1C candidate validation is available | pass | pass / 39 passed / 0 failed / 0 warnings | pass / 39 passed / 0 failed / 0 warnings |
| Candidate evidence | Candidate validation records the approved point, shadow, and interval policies | pass | {'point_policy': 'stable_candidate', 'shadow_policy': 'adaptive_shadow_only', 'interval_method': 'exp_weighted_q80'} | stable candidate / adaptive shadow only / exp_weighted_q80 |
| Live governance | Passing governed-live operational validation is available | pass | pass / 20 passed / 0 failed / 0 warnings | pass / 20 passed / 0 failed / 0 warnings |
| Live governance | Operational validation resolves to a successful persisted live run | pass | success | success |
| Governance linkage | Governed live run is linked to the passing candidate validation | pass | 0540c6ee-2d96-493a-adfe-a76c5c91cf31 | 0540c6ee-2d96-493a-adfe-a76c5c91cf31 |
| Live governance | Governed run contains exactly one headline for each labour target | pass | 3 targets; 0 duplicates | 3 targets; 0 duplicates |
| Policy governance | Live headlines follow the validated stable target-stage map | pass | 0 | 0 violations |
| Uncertainty calibration | All governed intervals use the validated prior-only method | pass | 0 | 0 methods other than exp_weighted_q80 |
| Challenger governance | Adaptive forecasts remain separate shadow outputs | pass | 0 | 0 missing shadow outputs |
| News decomposition | Comparable news decomposition exists for all three governed headlines | pass | 3 targets; 1 previous run IDs | 3 targets and at least 1 previous run |
| News decomposition | Labour news decomposition reconciles arithmetically | pass | 0.0 | <= 1e-08 |
| Reproducibility | Governed live run contains complete SHA-256 provenance controls | pass | 0 | 0 invalid hashes |
| Documentation | Candidate and operational validation reports are preserved | pass | {'candidate_report': True, 'operational_report': True} | both reports exist |
| Documentation | Model 1C model card is present | pass | C:\Users\Cenk\OneDrive\MacroPulse\docs\model1c_model_card_draft.md | file exists |

## Conclusion

The Model 1C candidate has passing pseudo-real-time candidate evidence, a passing governed live operational validation, complete provenance hashes, a comparable three-target news decomposition, and preserved validation reports. It is ready for explicit model-owner review and signoff. This assessment does not itself promote the model to production.