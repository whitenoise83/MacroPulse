# Changelog — Model 1C v1.0.0.post1

## Fixed

- Corrected the known positional-column defect in the persisted Model 1C
  governed-live operational-validation metadata.
- Added an idempotent, evidence-linked repair command.
- Made the production promotion command apply the safe repair automatically.
- Explicitly ordered operational-validation columns before future DuckDB writes.

## Unchanged

- The 20/20 operational validation result.
- Candidate validation, freeze assessment, forecasts, intervals, model policy,
  shadow forecasts, hashes, news decomposition, and reports.
