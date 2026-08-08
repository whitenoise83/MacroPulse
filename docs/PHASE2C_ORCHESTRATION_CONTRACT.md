# Phase 2C — Unified Governed Orchestration Contract

## Purpose

Phase 2C codifies the manual operational sequence already proven with real
MacroPulse data while preserving the governance boundary around Models 1A–1D.

The orchestrator does not implement model equations, estimators, selection
rules, or persistence logic. It calls the existing governed entry points.

## Default safety posture

`run_platform_operations.py` is a **dry run by default**.

```cmd
python scripts\\run_platform_operations.py
```

Mutation requires an explicit flag:

```cmd
python scripts\\run_platform_operations.py --execute
```

Model 1D requires an additional explicit opt-in:

```cmd
python scripts\\run_platform_operations.py --execute --run-model1d
```

The default operational command therefore cannot accidentally create a Model 1D
prospective observation.

## Governed order

Execution is:

1. verify the frozen Model 1D v0.3.8 release boundary;
2. refresh the release calendar;
3. re-evaluate Phase 2B freshness;
4. for each blocked production component only:
   - refresh its existing source-data path;
   - invoke its existing governed model entry point;
   - re-check that the component is fresh at the requested cutoff;
5. stop if any production component remains blocked;
6. evaluate the Model 1D monthly eligibility gate;
7. invoke Model 1D only when explicitly requested and eligible;
8. return a final read-only Phase 2B status.

A successful rerun when Models 1A–1C are already fresh does not create duplicate
production model runs.

## Current-day mutation rule

Model 1A's governed production entry point does not accept a historical
information cutoff and uses the current date internally. Therefore Phase 2C
fails closed when `--execute --as-of YYYY-MM-DD` is not today's date.

Historical dates remain available for dry-run/status inspection.

## Model 1D gate

Possible actions:

- `blocked_production_sources`
- `skip_existing_month`
- `resolve_due_outcomes_only`
- `create_monthly_prediction`
- `create_monthly_prediction_and_resolve_due_outcomes`

An existing state-month observation is never recreated. When only outcome
resolution is eligible, the existing Model 1D operation is invoked with
`--skip-prediction`.

Phase 2C never changes the Model 1D candidate, benchmark, target horizon,
probability method, release tags, or promotion authority.

## Failure semantics

- Unknown model identity/version/lifecycle: fail closed.
- Future operational cutoff: fail closed.
- Historical mutating cutoff: fail closed.
- Release-calendar command failure: stop.
- Source-data refresh failure: stop.
- Governed model command failure: stop before downstream operations.
- Component still stale after rerun: stop before Model 1D.
- Model 1D not requested: report eligibility only.
- Existing Model 1D month: skip prediction.
- Outcome not due: no resolution is attempted.

## Command outcomes

Each invoked command is recorded in the in-memory result with its step,
component, command, return code, status, captured stdout, and captured stderr.
`--json` emits the deterministic execution record. Phase 2C adds no database
table merely for orchestration logging.

Existing Model 1B and 1C validation services may create local Markdown
validation reports. Phase 2C does not delete or commit those artifacts.
