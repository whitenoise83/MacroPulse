# Phase 3E — Decision-Intelligence Presentation Contract

## Status

Phase 3E implementation contract.

Phase 3E composes already-governed evidence into CLI, deterministic snapshot,
and dashboard interfaces. It does not redefine forecast, outcome, performance,
revision, freshness, or release semantics.

## 1. Dependency contract

Phase 3E consumes:

```text
Phase 2D  deterministic platform snapshot
Phase 3B  first-release forecast-evaluation ledger
Phase 3C  target-specific accuracy/calibration/drift evidence
Phase 3D  same-target-period revision/release associations
```

Phase 3E is presentation and composition only.

## 2. User questions

The presentation layer must expose, where available:

- current governed forecast;
- current 80% interval;
- recent same-target-period revision;
- historical MAE/RMSE/bias context;
- empirical 80% coverage;
- directional accuracy where applicable;
- Phase 3C sample sufficiency;
- descriptive drift status;
- source freshness;
- due and upcoming releases;
- Phase 3D scheduled-release associations;
- evidence flags.

## 3. No semantic duplication

Phase 3E must not independently:

- resolve realised outcomes;
- calculate a new error convention;
- redefine comparable forecast identity;
- redefine drift windows;
- classify release associations as causal;
- create cross-target raw-error scores.

Those semantics belong to Phases 3B–3D.

## 4. Evidence flags

Evidence flags are deterministic presentation metadata.

Current flags are limited to evidence/readiness conditions:

```text
production_sources_not_ready
invalid_evaluation_rows
scheduled_source_releases_due
no_resolved_evaluation_history
insufficient_evaluation_history
```

Phase 3E does not convert a single MAE, bias, coverage observation, revision, or
drift ratio into a model warning.

An insufficient sample is displayed as insufficient evidence rather than as a
positive or negative performance judgement.

## 5. Current forecast evidence

Each current production target may combine:

- current governed run lineage;
- freshness;
- forecast and interval;
- current Phase 3B evaluation state;
- latest same-period Phase 3D revision;
- release-association counts;
- target-series Phase 3C historical context.

Metrics remain target-specific.

## 6. Deterministic snapshot

Snapshot schema:

```text
1.0.0
```

The semantic snapshot contains:

```text
summary
current_forecasts
evidence_flags
evaluation
performance
revisions
freshness
calendar
provenance
model1d_research
snapshot_hash
```

The hash excludes:

- export path;
- wall-clock generation timestamp.

For identical governed state and identical `as_of`, the semantic snapshot must
be identical.

## 7. CLI

Read-only report:

```cmd
python scripts\report_decision_intelligence.py --as-of YYYY-MM-DD
```

Full deterministic JSON to stdout:

```cmd
python scripts\report_decision_intelligence.py --as-of YYYY-MM-DD --json
```

## 8. Local export

```cmd
python scripts\export_decision_intelligence_snapshot.py --as-of YYYY-MM-DD
```

Default path:

```text
reports/decision_intelligence_snapshots/
```

The directory is git-ignored.

Export changes no model or database state.

## 9. Dashboard

The Streamlit navigation adds:

```text
Forecast Intelligence
```

The dashboard is read-only and displays the same deterministic snapshot
available through the CLI/export interfaces.

The JSON download button serialises the already-built in-memory snapshot.

## 10. Model 1D separation

Model 1D may appear only in a visually separated research section.

Phase 3E does not:

- evaluate Model 1D as production;
- mix its evidence with 1A–1C accuracy metrics;
- tune its candidate/comparator;
- create promotion authority.

## 11. Generative-AI boundary

No generative-AI text is part of the governed Phase 3E evidence snapshot.

Any future natural-language explanation must remain downstream, clearly
non-governing, and reproducible evidence must remain available without it.

## 12. Mutation boundary

Phase 3E must not:

- initialise/migrate the database;
- download source data;
- execute Models 1A–1D;
- mutate governed forecasts;
- mutate source observations;
- alter production status;
- automatically promote/demote/switch models.
