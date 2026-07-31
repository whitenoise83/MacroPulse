# MacroPulse Model 1B v0.6.0.post1 — Freeze Assessment Tooling

This narrow governance update adds `scripts/generate_inflation_freeze_assessment.py`.
It does not change Model 1B forecasts, policy selection, intervals, news attribution,
configuration, or the v0.6.0 governed-live model identity.

The assessment verifies the passing 28-check candidate validation, passing 20-check
operational validation, linkage to the governed live run, stable-policy control,
shadow separation, exp-weighted prior-only intervals, four-target comparable news
reconciliation, provenance hashes, and preserved reports.

Run:

```cmd
python scripts\generate_inflation_freeze_assessment.py ^
  --candidate-validation-id 5f0cd6ea-c41f-44da-a21a-43490d8e75ce ^
  --operational-validation-id 58c89931-0f6b-43ed-8815-abbc99fa4ac8
```

Expected readiness: `ready_for_model_owner_signoff`.
