# MacroPulse Model 1C v1.0.0 — Production Release

This release promotes `US_LABOUR_NOWCAST_1C` from the validated governed-live
candidate to owner-approved production.

## Evidence chain

- Candidate validation: `0540c6ee-2d96-493a-adfe-a76c5c91cf31` — 39/39
- Operational validation: `f535fdc2-c75c-4da8-a0f8-e3d1b80416f3` — 20/20
- Freeze assessment: `7eb22dae-54c8-423e-ad1e-9977db08d388` — 14/14
- Governed live run: `56adddf6-2438-43cf-97b0-24e4801ac9a4`
- Owner decision: `APPROVE MODEL 1C FREEZE`

## Install

```cmd
pip install -e .
python scripts\initialise_database.py
python scripts\promote_model1c_v1.py
```

The promotion command verifies the full evidence chain against the local
DuckDB database and is idempotent.
