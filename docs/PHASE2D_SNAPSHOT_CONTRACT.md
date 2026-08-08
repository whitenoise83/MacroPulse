# Phase 2D — Deterministic Macro Snapshot Contract

## Purpose

Phase 2D converts already-persisted governed MacroPulse state into one
deterministic decision-support snapshot. It is a composition/export layer, not a
model and not an orchestration layer.

## Determinism

For the same persisted database state and the same `as_of` date, the semantic
snapshot and `snapshot_hash` are identical.

The semantic hash excludes wall-clock export time, output path and formatting
whitespace. The canonical snapshot therefore contains no generated-at clock
timestamp.

## Boundary

Snapshot construction uses the existing read-only repository query path and the
Phase 2B status collector. It does not:

- download source data;
- run, retrain or select a model;
- create or replace a Model 1D prospective observation;
- resolve Model 1D outcomes;
- mutate DuckDB;
- change database schema;
- move or recreate release tags.

The only write is the requested JSON export file.

## Schema v1.0.0

The snapshot contains:

- readiness and component state;
- current governed 1A/1B/1C forecasts;
- previous governed run IDs;
- comparable forecast revisions;
- target/stage changes;
- frozen Model 1D run, predictions, probabilities and dimensions;
- source health and due releases;
- upcoming releases;
- persisted provenance/hashes;
- deterministic snapshot hash.

A forecast delta is emitted only when current and previous runs refer to the
same target period. When the target period changes, `forecast_change` is null
and `comparable_forecast` is false.

## Export

```cmd
python scripts\export_macro_snapshot.py --as-of 2026-08-08
```

Default output:

```text
reports/macro_snapshots/macro_snapshot_20260808.json
```

`reports/macro_snapshots/` is ignored by Git because these JSON files are local
operational derivatives of governed persisted state.
