# MacroPulse Model 1D v0.3.8 — Prospective Shadow Research Release

Model `US_MACRO_STATE_1D` v0.3.8 is an operational prospective-shadow research
release. It collects immutable, genuinely ex-ante evidence comparing the frozen
Model 1D v0.3.6 source candidate with the causal `rolling_frequency` benchmark.

It is not a production release and has no promotion, switching, blending, or
source-replacement authority.

## Frozen experiment

- Parent release: `0.3.7`
- Frozen source version: `0.3.6`
- Frozen source candidate:
  `expanding_robust_z__policy__equal__sensitive__independent_normal`
- Primary comparator: `rolling_frequency`
- Target: fixed-horizon 90-day vintage
- Probability families:
  `adverse_supply`, `benign_expansion`, `contraction`,
  `inflationary_expansion`, and `mixed`
- Formal comparison gate: at least 12 complete prospective target months
- Before the gate: `insufficient_prospective_evidence`

For every state month, the workflow stores exactly one run, two benchmark
predictions, and three dimension-lineage rows. Once the fixed-horizon target is
genuinely available, it appends exactly two outcome rows without mutating the
prediction package.

## First prospective observation

- Shadow run ID: `73ea26fd-a731-4d87-a735-ae1107a9c06c`
- Information cutoff: `2026-08-05`
- State date: `2026-08-31`
- Expected target availability: `2026-11-29`
- Source prediction: `contraction`
- Rolling-frequency prediction: `benign_expansion`
- Information-set hash:
  `3c0ca752574ca5a4b7d9e8713a29a4a274b1b06ff50d3fceed77aa30af8cec74`
- Source-bundle hash:
  `d8344c4ed94cc6502da81c04dfd7dc1e73c35499b9405af0ad22f2cf787735ba`
- Outcome rows at operational freeze: `0`

The first prediction was successfully protected against duplicate monthly
execution and premature outcome resolution.

## Operational identity

- Operational implementation commit: `6e1ff2a`
- Operational tag: `model1d-v0.3.8-prospective-shadow-operational`
- Repository-hygiene commit: `252caaf`
- Lifecycle: `development`
- Evidence type: `prospective_shadow`
- Promotion authority: `none`

The operational tag intentionally remains on the implementation commit. Later
documentation or ignore-rule commits must not move that tag.

## Monthly workflow

After the governed Model 1A, Model 1B, and Model 1C source runs are available:

```cmd
python scripts\run_macro_state_shadow_operations.py
```

Read-only status:

```cmd
python scripts\report_macro_state_shadow_status.py --no-write
```

Dashboard:

```cmd
streamlit run app.py
```

Open **Model 1D Shadow**.

## Local evidence protection

The DuckDB evidence store and its backups are local operational artifacts:

```text
data/macropulse.duckdb
data/backups/
reports/macro_state_shadow_monitoring/
```

They must not be committed to the public repository. Database backups should be
taken only while Streamlit and other DuckDB writers are closed.

## Governance boundary

This release may not:

- change the frozen v0.3.6 source specification;
- tune against prospective outcomes;
- backfill predictions using revised information;
- overwrite or delete shadow records;
- resolve outcomes before all required fixed-horizon evidence is available;
- approve production use, adaptive switching, or blending;
- merge Model 1D into production.

Any later candidate or production decision requires a separate governed release
after the prospective evidence gate is satisfied.
