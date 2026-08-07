# MacroPulse Phase II Architecture

## Purpose

Phase II separates model science from platform operations.

The model layer owns equations, transformations, estimation, uncertainty,
candidate selection, validation, and model-specific governance.

The Phase II platform layer owns read-only discovery, freshness, orchestration,
cross-model status, deterministic snapshots, and presentation.

## Component boundaries

### Existing governed components

- Model 1A production GDP nowcast.
- Model 1B production inflation nowcast.
- Model 1C production labour nowcast.
- Model 1D v0.3.8 prospective-shadow research workflow.

Phase II treats these as upstream governed systems.

### New platform components

Proposed package namespace:

```text
src/macropulse/platform/
    __init__.py
    status.py
    freshness.py
    orchestration.py
    snapshot.py
```

Proposed commands:

```text
scripts/report_platform_status.py
scripts/run_platform_operations.py
scripts/export_macro_snapshot.py
```

These names are architectural targets, not yet implemented in Phase 2A.

## Service contracts

### PlatformStatus

A read-only object describing:

- component identifier;
- lifecycle state;
- governed version;
- latest run identifier;
- latest state/target date;
- information cutoff;
- freshness state;
- integrity state;
- blocking issues.

### PlatformReadiness

A read-only decision containing:

- `ready`;
- blocking prerequisites;
- stale components;
- missing components;
- next scheduled release context.

Readiness is operational, not a model recommendation.

### MacroSnapshot

A deterministic serialization of persisted model outputs at a single explicit
information cutoff.

The same snapshot payload must drive CLI exports and the dashboard.

## Data policy

Phase II should prefer reads from existing persisted governed tables and
repositories.

Schema additions require a separate migration only when read-only derivation is
insufficient. Do not introduce a new database table merely to simplify UI code.

Generated reports remain local artifacts unless a later release explicitly
governs them as committed fixtures.

## Failure policy

- Missing governed output -> explicit blocked state.
- Stale source -> explicit stale state.
- Model command failure -> stop dependent operations.
- Model 1D not eligible -> skip safely; never synthesize a prediction.
- Outcome not available -> no-op; never resolve early.
- Unknown lifecycle/version -> fail closed.

## Testing policy

Tests should use synthetic repositories/fixtures and assert:

- read-only methods do not mutate governed tables;
- stale and missing states are deterministic;
- orchestration order respects dependencies;
- failures stop downstream execution;
- repeated safe runs are idempotent;
- Model 1D boundaries remain intact.

## Out of scope for initial Phase II

- new macroeconomic model families;
- automatic trade/investment recommendations;
- LLM-generated governed outputs;
- automatic production promotion;
- cloud deployment;
- multi-user authentication;
- external notification delivery.

Those may be evaluated after the operational platform is stable.
