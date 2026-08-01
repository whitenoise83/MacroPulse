# MacroPulse Model 1C v0.6.0.post1 — Freeze Assessment Tooling

This narrow governance update adds:

```text
scripts/generate_labour_freeze_assessment.py
```

It does not change Model 1C forecasts, stable-policy selection, adaptive-shadow
selection, intervals, news attribution, configuration, or the v0.6.0 governed-live
model identity.

The assessment verifies:

- the passing 39-check Model 1C candidate validation;
- the passing 20-check governed-live operational validation;
- linkage to the validated governed live run;
- stable-policy control over all three labour targets;
- adaptive forecasts remaining shadow-only;
- prior-only `exp_weighted_q80` intervals;
- comparable three-target labour-news reconciliation;
- complete provenance hashes;
- preserved candidate and operational reports;
- availability of the Model 1C model card.

Example:

```cmd
python scripts\generate_labour_freeze_assessment.py ^
  --candidate-validation-id 0540c6ee-2d96-493a-adfe-a76c5c91cf31 ^
  --operational-validation-id f535fdc2-c75c-4da8-a0f8-e3d1b80416f3
```

Expected readiness:

```text
ready_for_model_owner_signoff
```

This assessment records freeze readiness only. It does not promote Model 1C to
production.
