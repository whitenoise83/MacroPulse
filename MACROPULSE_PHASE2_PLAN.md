# MacroPulse Phase II — Platform Integration & Decision Support

Status: specification bootstrap
Branch: `phase2-platform-development`
Base: Model 1D v0.3.8 protected research branch at `048c1a6`

## 1. Objective

Phase I established the governed current-state model suite:

- Model 1A — US GDP Nowcast: production v1.0.0.
- Model 1B — US Inflation Nowcast: production v1.0.0.
- Model 1C — US Labour Nowcast: production v1.0.0.
- Model 1D — Unified US Macro State: development v0.3.8 prospective shadow.

Phase II does not create a new macro model. It turns the existing governed model
suite into a safer and more useful operational platform.

The primary Phase II deliverable is a deterministic decision-support layer that
can answer, from the governed local evidence store:

1. What is the latest valid state of each governed model?
2. How fresh is each model and each required source?
3. What changed since the previous governed run?
4. Which releases are due next?
5. Is the platform safe to run downstream operations?
6. What concise macro snapshot can be exported without changing model state?

## 2. Non-negotiable boundaries

Phase II must not:

- change Model 1A, 1B, or 1C production specifications without their normal
  challenger/revalidation/owner-approval process;
- change the frozen Model 1D v0.3.8 source candidate, benchmark, target,
  probability contract, persistence rules, or outcome resolver;
- tune any model against Model 1D prospective outcomes;
- backfill prospective Model 1D predictions;
- move either published Model 1D v0.3.8 release tag;
- commit local DuckDB databases, database backups, or generated Model 1D
  monitoring reports;
- allow an orchestration layer to silently overwrite governed model outputs.

Model 1D remains research-only until its independent prospective evidence gate
is satisfied under a later governed release.

## 3. Phase II workstreams

### Phase 2A — Bootstrap and platform contract

Deliverables:

- isolated `phase2-platform-development` branch;
- frozen Phase II scope and architecture documents;
- machine-readable Phase II boundary metadata;
- bootstrap contract tests.

No model logic or database schema changes.

### Phase 2B — Read-only system health and freshness

Build a read-only platform-status service that reports:

- latest governed run for Models 1A, 1B, and 1C;
- latest Model 1D prospective-shadow run and evidence count;
- information cutoffs and target/state periods;
- source freshness and missing/stale requirements;
- upcoming release-calendar items;
- integrity/readiness flags.

First implementation must be read-only. It may write an optional report file,
but it may not create or mutate model predictions.

### Phase 2C — Unified governed orchestration

Add one guarded command for routine operations.

The orchestrator must:

- expose an explicit dry-run/status mode;
- call existing governed model entry points rather than reimplement models;
- stop on failed prerequisite or stale/incomplete data;
- record which component commands ran and their exit status;
- invoke Model 1D shadow operations only after eligible governed source runs;
- preserve each component model's independent governance identity;
- be idempotent where the underlying component operation is idempotent.

No automatic production promotion.

### Phase 2D — Deterministic macro snapshot

Create a reproducible current-state snapshot generated only from persisted,
governed outputs.

Minimum contents:

- GDP nowcast and uncertainty/status;
- inflation target nowcasts and status;
- labour target nowcasts and status;
- Model 1D research-state probabilities/status clearly labelled research-only;
- information-cutoff timestamps;
- changes from the previous comparable run;
- release-calendar horizon;
- explicit stale/missing-data warnings.

Outputs:

- JSON for machine use;
- Markdown for human review;
- optional CSV tables.

The snapshot must not contain generative-AI interpretation in its governed core.

### Phase 2E — Integrated dashboard

Add a platform overview that consumes the same read-only status/snapshot
services used by the CLI.

The UI must:

- distinguish production from research models;
- expose freshness and lineage before headline numbers;
- show stale or incomplete states prominently;
- never present Model 1D v0.3.8 as production;
- remain read-only with respect to governed model predictions.

### Phase 2F — Operational hardening

Add:

- CI for Phase II platform contracts;
- report-schema tests;
- failure-mode tests;
- orchestration dry-run tests;
- documentation/runbook;
- release manifest and validation record.

## 4. Architectural rule

Phase II is an orchestration and presentation layer above the governed model
services. It must consume stable public/service interfaces where possible.

Do not duplicate model equations in the platform layer.

Preferred dependency direction:

```text
data / release calendar
        |
governed model services (1A, 1B, 1C)
        |
persisted governed outputs
        |
Phase II status + orchestration + snapshot services
        |
CLI / reports / Streamlit
        |
Model 1D shadow operations consume governed source outputs independently
```

Model 1D's frozen prospective-shadow engine remains under its existing release
contract; Phase II may display and operationally invoke it but may not alter it.

## 5. Phase II initial acceptance criteria

Before Phase 2A closes:

- branch is `phase2-platform-development`;
- branch descends from protected commit `048c1a6`;
- Model 1D release verifier passes before branching;
- Phase II scope is machine-readable;
- bootstrap tests pass;
- full repository tests still pass;
- working tree is clean after commit;
- frozen Model 1D tags remain unchanged.

## 6. Release discipline

Phase II versioning belongs to the platform layer. It does not increment Model
1A, 1B, 1C, or 1D versions by itself.

Any future material model change must happen in a separately governed model
release with its own evidence and approval.
