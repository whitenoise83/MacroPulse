# MacroPulse Model 1B Freeze Assessment

- Assessment ID: `2b7fe987-384a-451b-971f-03d5bf5106c7`
- Readiness: **ready_for_model_owner_signoff**
- Candidate validation ID: `5f0cd6ea-c41f-44da-a21a-43490d8e75ce`
- Operational validation ID: `58c89931-0f6b-43ed-8815-abbc99fa4ac8`
- Governed live run ID: `905deade-2bbf-4c89-801e-ce296bb00d97`
- Vintage backtest ID: `fdd2f573-a425-4abc-8056-f9843955bac2`
- Governed live model version: `0.6.0`
- Stable policy decisions: `16`
- Interval method: `exp_weighted_q80`
- Adaptive selector: `shadow challenger only`

## Freeze checks

| Gate | Check | Status | Observed | Threshold |
|---|---|---:|---:|---:|
| Candidate evidence | Passing Model 1B candidate validation is available | pass | pass / 28 passed / 0 failed / 0 warnings | pass / 28 passed / 0 failed / 0 warnings |
| Candidate evidence | Candidate validation records the approved point, shadow, and interval policies | pass | {'point_policy': 'stable_candidate', 'shadow_policy': 'adaptive_shadow_only', 'interval_method': 'exp_weighted_q80'} | stable candidate / adaptive shadow only / exp_weighted_q80 |
| Live governance | Passing governed-live operational validation is available | pass | pass / 20 passed / 0 failed / 0 warnings | pass / 20 passed / 0 failed / 0 warnings |
| Live governance | Operational validation resolves to a successful persisted live run | pass | success | success |
| Governance linkage | Governed live run is linked to the passing candidate validation | pass | 5f0cd6ea-c41f-44da-a21a-43490d8e75ce | 5f0cd6ea-c41f-44da-a21a-43490d8e75ce |
| Live governance | Governed run contains exactly one headline for each inflation target | pass | 4 targets; 0 duplicates | 4 targets; 0 duplicates |
| Policy governance | Live headlines follow the validated stable target-stage map | pass | 0 | 0 violations |
| Uncertainty calibration | All governed intervals use the validated prior-only method | pass | 0 | 0 methods other than exp_weighted_q80 |
| Challenger governance | Adaptive forecasts remain separate shadow outputs | pass | 0 | 0 missing shadow outputs |
| News decomposition | Comparable news decomposition exists for all four governed headlines | pass | 4 targets; 1 previous run IDs | 4 targets and at least 1 previous run |
| News decomposition | Inflation news decomposition reconciles arithmetically | pass | 0.0 | <= 1e-08 |
| Reproducibility | Governed live run contains complete SHA-256 provenance controls | pass | 0 | 0 invalid hashes |
| Documentation | Candidate and operational validation reports are preserved | pass | {'candidate_report': True, 'operational_report': True} | both reports exist |
| Documentation | Model 1B model card is present | pass | C:\Users\Cenk\OneDrive\MacroPulse\docs\model1b_model_card_draft.md | file exists |

## Conclusion

The Model 1B candidate has passing pseudo-real-time candidate evidence, a passing governed live operational validation, complete provenance hashes, a comparable four-target news decomposition, and preserved validation reports. It is ready for explicit model-owner review and signoff. This assessment does not itself promote the model to production.