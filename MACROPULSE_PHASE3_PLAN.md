# MacroPulse Phase III — Forecast Evaluation & Decision Intelligence

Status: specification bootstrap

Branch: `phase3-evaluation-development`

Base release: `phase2-platform-v1.0.0`

Base commit: `43395d889a76453706259a5095bd718337b55851`

## 1. Objective

Phase II established a released, governed operational platform over Models
1A–1D. Phase III adds an evidence and interpretation layer above that released
baseline.

Phase III must answer, deterministically and reproducibly:

1. How have the governed production forecasts performed against defined
   realised outcomes?
2. How large and how frequent are forecast revisions?
3. Which scheduled data releases coincide with material forecast changes?
4. Are bias, error, interval coverage, or freshness patterns deteriorating?
5. What evidence should a user inspect before relying on the current forecast?
6. Can the same evidence be exported and displayed without changing governed
   model state?

Phase III is not a model-retuning phase.

## 2. Non-negotiable boundaries

Phase III must not:

- change Model 1A, 1B, or 1C production specifications without their normal
  challenger/revalidation/owner-approval process;
- change the frozen Model 1D v0.3.8 candidate, comparator, target, horizon,
  probability contract, persistence rules, or outcome resolver;
- use Model 1D prospective outcomes to tune, switch, blend, calibrate, or
  promote a candidate;
- backfill Model 1D prospective predictions;
- move or recreate published Model 1D release tags;
- move or recreate the Phase II release tag;
- silently redefine realised outcomes used for forecast evaluation;
- mix first-release and revised outcomes without explicit labelling;
- turn monitoring thresholds into automatic model promotion/demotion;
- write governed model predictions from the evaluation layer;
- commit local DuckDB files, backups, generated monitoring reports, or local
  evaluation exports.

Model 1D remains research-only until its independent prospective evidence gate
is satisfied under its own governed release.

## 3. Evaluation principles

### 3.1 Outcome identity

Every evaluated forecast must identify:

- model and version;
- governed run ID;
- information cutoff;
- target period;
- target variable;
- outcome definition;
- outcome vintage;
- outcome availability date;
- evaluation timestamp.

Where economically meaningful, first-release outcomes should be the default
real-time evaluation target. Revised outcomes may be displayed separately but
must never be silently substituted.

### 3.2 No-look-ahead

A forecast may only be evaluated against an outcome that was genuinely
available according to the declared evaluation contract.

### 3.3 Deterministic metrics

Core evaluation metrics must be deterministic from persisted governed
forecasts and declared realised outcomes.

### 3.4 Monitoring is not adaptation

A deterioration flag may trigger human review. It must not automatically alter
model selection, coefficients, transformations, intervals, thresholds, or
production status.

## 4. Workstreams

### Phase 3A — Bootstrap and evidence contract

Deliverables:

- isolated Phase III development branch from the Phase II v1.0.0 tag;
- frozen Phase III scope and architecture;
- machine-readable Phase III boundary metadata;
- bootstrap contract tests.

No model logic or database schema changes.

### Phase 3B — Production forecast evaluation ledger

Build a deterministic evaluation service for Models 1A–1C.

Minimum capabilities:

- link governed forecasts to declared realised outcomes;
- preserve outcome-vintage identity;
- compute forecast error only when the outcome is available;
- distinguish unresolved from resolved observations;
- expose run/target/cutoff lineage;
- remain read-only with respect to governed forecast tables.

Any persisted evaluation table introduced later must be append-only and must
not alter governed model outputs.

### Phase 3C — Accuracy, calibration, and drift monitoring

Provide deterministic summaries including, where applicable:

- MAE;
- RMSE;
- mean error / bias;
- median absolute error;
- directional accuracy for changes;
- interval empirical coverage;
- interval width;
- rolling-window metrics;
- target-stage / forecast-horizon breakdowns;
- insufficient-sample flags.

Monitoring thresholds must be documented and must not create automatic
production actions.

### Phase 3D — Revision and release-impact analytics

Build revision diagnostics over governed run history:

- current versus previous comparable forecast;
- cumulative revision within a target period;
- revision distribution by target stage/horizon;
- linkage to the governed release calendar;
- release-window attribution as descriptive evidence.

Release-impact analytics must distinguish temporal association from causal
identification unless a separately governed causal design exists.

### Phase 3E — Decision-intelligence presentation layer

Expose the evaluation evidence through CLI/snapshot/dashboard interfaces.

The user-facing layer should answer:

- current forecast;
- recent revision;
- historical error context;
- calibration/coverage status;
- freshness;
- upcoming releases;
- evidence warnings.

Model 1D may be displayed only as research/prospective evidence and must remain
visually separated from production evaluation.

No generative-AI text may become part of the governed evaluation core.

### Phase 3F — Operational hardening and release

Add:

- Phase III CI guard;
- evaluation-schema tests;
- no-look-ahead tests;
- outcome-vintage tests;
- failure-mode tests;
- deterministic export tests;
- operational runbook;
- release manifest;
- validation record.

## 5. Architecture

Preferred dependency direction:

```text
governed source data + release calendar
                |
governed Models 1A / 1B / 1C
                |
persisted governed forecasts
                |
declared realised outcomes / vintages
                |
Phase III evaluation services
                |
accuracy / calibration / revision / drift
                |
CLI / deterministic export / dashboard
```

Model 1D prospective evidence remains an independent research path and is not a
source of adaptive decisions for Phase III.

## 6. Initial Phase 3A acceptance criteria

Before Phase 3A closes:

- branch is `phase3-evaluation-development`;
- branch descends exactly from released Phase II tag
  `phase2-platform-v1.0.0`;
- Phase II release verifier passes with `--require-tag`;
- Model 1D v0.3.8 release verifier passes with `--require-tags`;
- Phase III boundary metadata is machine-readable;
- bootstrap contract tests pass;
- full repository tests still pass;
- no model implementation file is changed;
- no database schema is changed;
- working tree is clean after commit.

## 7. Release discipline

Phase III versioning belongs to the evaluation/decision-intelligence layer. It
does not increment Models 1A, 1B, 1C, or 1D by itself.

Any model modification remains a separate governed model release.
