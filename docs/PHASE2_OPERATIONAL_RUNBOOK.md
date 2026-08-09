# MacroPulse Phase II Operational Runbook

## 1. Purpose

This runbook is for routine operation of the Phase II platform layer. It does
not authorise changes to Models 1A–1D.

The platform boundary remains:

- Models 1A–1C: production v1.0.0;
- Model 1D: development v0.3.8 prospective shadow;
- Model 1D promotion authority: none.

## 2. Pre-operation checks

From the repository root:

```cmd
git status --short
python scripts\verify_model1d_v038_release.py --require-tags
python scripts\verify_phase2_platform.py --require-model1d-tags
python scripts\report_platform_status.py
```

Do not begin a mutating platform operation when:

- the working tree contains unexpected tracked modifications;
- either release verifier fails;
- the status service reports a blocked production source;
- lifecycle/version identity is unknown.

## 3. Read-only inspection

Platform status:

```cmd
python scripts\report_platform_status.py
```

Historical status:

```cmd
python scripts\report_platform_status.py --as-of YYYY-MM-DD
```

Orchestration plan:

```cmd
python scripts\run_platform_operations.py
```

Deterministic snapshot:

```cmd
python scripts\export_macro_snapshot.py --as-of YYYY-MM-DD
```

Dashboard:

```cmd
streamlit run app.py
```

The Platform Overview page is read-only.

## 4. Governed production operation

First inspect the dry run:

```cmd
python scripts\run_platform_operations.py
```

Then execute current-day production operations:

```cmd
python scripts\run_platform_operations.py --execute
```

Phase 2C fails closed for historical mutation because Model 1A does not expose a
historical cutoff through its governed CLI.

Do not manually re-run individual production scripts after a successful unified
operation unless investigating a documented failure.

## 5. Model 1D operation

Model 1D is not part of the default production operation.

Inspect eligibility:

```cmd
python scripts\run_platform_operations.py --run-model1d
```

Only when a genuine new prospective state month is due and governed production
sources are ready:

```cmd
python scripts\run_platform_operations.py --execute --run-model1d
```

An existing state-month observation must produce `skip_existing_month`.

Never regenerate a prospective observation merely because newer Models 1A–1C
runs exist.

## 6. Failure recovery

### Release verifier fails

Stop. Do not run governed model operations.

Inspect:

```cmd
git status --short
git --no-pager diff
git --no-pager log -10 --oneline --decorate
```

Do not move or recreate Model 1D release tags as a repair.

### Source refresh fails

The orchestrator stops downstream execution. Correct the source/download
failure, re-run the dry plan, then re-run the unified operation.

Do not manually mark a component ready.

### Governed model command fails

The orchestrator stops before later dependent operations. Preserve the command
output, fix the underlying model/service issue, and rerun from the unified
entry point.

### Component remains stale after a successful command

Treat this as a blocked state. Do not invoke Model 1D. Inspect source freshness
and due releases using:

```cmd
python scripts\report_platform_status.py
```

### Snapshot export fails

Snapshot export is read-only with respect to governed state. Fix the read/schema
problem before changing any model output.

### Dashboard fails

Use the CLI status and snapshot commands first. The dashboard is presentation
only; do not repair a dashboard error by changing persisted model state.

## 7. Post-operation checks

```cmd
python scripts\report_platform_status.py
python scripts\verify_phase2_platform.py --require-model1d-tags
python scripts\verify_model1d_v038_release.py --require-tags
git status --short
```

New generated snapshots and operational reports must remain untracked.

Historical operational-validation reports that were already tracked at the
protected Phase II base commit `048c1a6` are grandfathered evidence. Phase II
does not delete or rewrite that pre-existing evidence; the release guard blocks
new tracked operational artifacts introduced after the protected base.

## 8. Monthly prospective evidence discipline

Model 1D remains frozen while prospective evidence accumulates.

- one immutable observation per genuine state month;
- no backfill;
- no candidate switching;
- no benchmark switching;
- no probability recalibration;
- no tuning on prospective outcomes;
- no production promotion from this runbook.

Formal comparison remains governed separately after the required prospective
evidence window.

## 9. CI

The `Phase II Platform Guard` workflow runs on the Phase II development branch
and pull requests. It verifies:

- frozen Model 1D boundary;
- Phase II platform contract;
- focused Phase II contract tests;
- complete repository tests;
- post-test boundary verification;
- no tracked source mutation during tests.

A failed guard is a release blocker.
