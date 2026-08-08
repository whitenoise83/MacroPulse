# Phase 2E — Integrated Platform Dashboard Contract

## Purpose

Phase 2E adds one integrated Streamlit decision-support page over the
deterministic Phase 2D snapshot.

The dashboard is a presentation layer. It is not allowed to become an
independent source of model, freshness, readiness, revision, or Model 1D
business logic.

## Data path

```text
persisted governed database
        |
Phase 2B status/freshness
        |
Phase 2D deterministic snapshot
        |
Phase 2E dashboard presentation
```

The dashboard calls `build_macro_snapshot()` and renders the resulting snapshot.

## Read-only boundary

The Phase 2E page must not:

- call `repository.initialise()`;
- issue direct SQL via `query_df`;
- download source data;
- run Models 1A, 1B or 1C;
- run or regenerate Model 1D;
- resolve Model 1D outcomes;
- mutate the database;
- change release tags;
- provide promotion controls.

The JSON download button serialises the already-built in-memory snapshot. It
does not persist a new database object or model output.

## Dashboard sections

1. platform readiness metrics;
2. component readiness table;
3. current governed 1A/1B/1C forecasts;
4. changes since previous governed runs;
5. frozen Model 1D prospective state;
6. source freshness and due releases;
7. upcoming release calendar;
8. governed provenance;
9. deterministic snapshot hash and JSON download.

## Revision semantics

The dashboard inherits Phase 2D comparison semantics. It displays a numerical
forecast revision only when current and previous governed runs share the same
target period.

Target-period changes are shown separately and are not labelled as forecast
revisions.

## Model 1D semantics

Model 1D is explicitly labelled research-only.

Newer 1A/1B/1C source runs may exist while the stored prospective observation
remains frozen. The dashboard surfaces
`source_run_advance_detected` without interpreting it as shadow staleness.

The page contains no Model 1D run button.
