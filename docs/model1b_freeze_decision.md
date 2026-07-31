# Model 1B Freeze Decision

- Candidate package version: `0.6.0.post1`
- Validated governed-live model version: `0.6.0`
- Promoted production version: `1.0.0`
- Candidate validation ID: `5f0cd6ea-c41f-44da-a21a-43490d8e75ce`
- Operational validation ID: `58c89931-0f6b-43ed-8815-abbc99fa4ac8`
- Freeze assessment ID: `2b7fe987-384a-451b-971f-03d5bf5106c7`
- Governed live run ID: `905deade-2bbf-4c89-801e-ce296bb00d97`
- Freeze report: `reports/inflation_freeze/model1b_freeze_assessment_20260731_110552.md`
- Decision date: `2026-07-31`
- Approval phrase: `APPROVE MODEL 1B FREEZE`

## Automated evidence

- Candidate validation: 28 passed, 0 failed, 0 warnings
- Operational validation: 20 passed, 0 failed, 0 warnings
- Freeze assessment: 14 passed, 0 failed, 0 warnings
- Freeze readiness: `ready_for_model_owner_signoff`

## Decision

- [x] Promote to `US_INFLATION_NOWCAST_1B v1.0.0`
- [ ] Remain a freeze candidate
- [ ] Reject and return to development

## Approved governance

- [x] Stable 16-decision target-stage map controls production headlines
- [x] Adaptive selector remains shadow-only
- [x] `exp_weighted_q80` is the production interval method
- [x] Prior-only selection and calibration controls remain mandatory
- [x] Provenance hashes and governance signatures remain mandatory
- [x] News reconciliation remains an operational gate
- [x] Material changes require a new validation and approval cycle
