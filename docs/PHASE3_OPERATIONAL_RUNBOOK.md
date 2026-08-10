# MacroPulse Phase III Operational Runbook

## 1. Purpose

This runbook governs routine use of the Phase III forecast-evaluation and
decision-intelligence layer. Phase III evaluates and presents evidence. It does
not authorise model changes.

Frozen boundary:

- Models 1A, 1B, 1C: production v1.0.0;
- Model 1D: development v0.3.8 prospective shadow;
- Model 1D promotion authority: none.

## 2. Pre-operation checks

```cmd
git status --short
python scripts\verify_phase2_release.py --require-tag
python scripts\verify_model1d_v038_release.py --require-tags
python scripts\verify_phase3_evaluation.py
```

Do not proceed when a frozen release verifier fails, Phase III boundary
verification fails, unexpected tracked changes exist, or outcome-vintage
identity is unclear.

## 3. Evidence dependency

```text
governed 1A/1B/1C forecasts
        |
explicit first-release identity
        |
exact release-date historical snapshot
        |
Phase 3B evaluation ledger
        |
Phase 3C target-specific performance
        |
Phase 3D same-target-period revisions
        |
Phase 3E deterministic presentation
```

Do not bypass an upstream semantic layer from a downstream interface.

## 4. Refreshing outcome evidence

The evaluation service is read-only. When new first-release outcomes become
available, refresh governed FRED/ALFRED evidence first, then cache only required
release-date snapshots:

```cmd
python scripts\refresh_phase3_outcome_snapshots.py --as-of YYYY-MM-DD
```

The refresher may write `historical_snapshots`; it must not run Models 1A–1D,
rewrite governed forecasts, or substitute latest/revised values. A second run
for already-cached required snapshots should be idempotent.

## 5. Evaluation ledger

```cmd
python scripts\report_forecast_evaluation.py --as-of YYYY-MM-DD
```

Respect statuses:

- `resolved`;
- `unresolved_*`;
- `structurally_unavailable`;
- `invalid_*`.

Do not use a latest/revised observation to force an unresolved row to resolved.

## 6. Accuracy, calibration and drift

```cmd
python scripts\report_forecast_performance.py --as-of YYYY-MM-DD --breakdowns
```

Raw MAE/RMSE/bias remain target-series-specific. Do not pool heterogeneous
units. Sample sufficiency and drift are monitoring evidence only; they do not
alter production state.

## 7. Revision and release evidence

```cmd
python scripts\report_forecast_revisions.py --as-of YYYY-MM-DD --events
```

Comparable identity is:

```text
component + target_series + target_period
```

The scheduled-release window is `(previous cutoff, current cutoff]`.
Association is descriptive. `information_set_advanced=True` does not establish
causal attribution.

## 8. Decision-intelligence snapshot

```cmd
python scripts\report_decision_intelligence.py --as-of YYYY-MM-DD
python scripts\report_decision_intelligence.py --as-of YYYY-MM-DD --json
python scripts\export_decision_intelligence_snapshot.py --as-of YYYY-MM-DD
```

Exports under `reports/decision_intelligence_snapshots/` must remain untracked.
For identical governed state and identical `as_of`, semantic JSON/hash must be
deterministic.

## 9. Dashboard

```cmd
streamlit run app.py
```

Use `Forecast Intelligence`. The dashboard is presentation-only and not a
model-control surface.

## 10. Evidence warnings

Warnings indicate evidence/readiness conditions such as insufficient history,
no resolved history, stale source state, due releases, or invalid evaluation
rows. They are not production-model failures, causal explanations, or
promotion/demotion authority.

## 11. Model 1D

Model 1D remains a separate prospective research path. Phase III must not score
it as production, mix it into 1A–1C metrics, regenerate an existing prospective
month, backfill, tune candidate/comparator choices, recalibrate probabilities,
or promote it.

## 12. Failure recovery

Missing first-release evidence: do not use latest/revised data; refresh initial
vintage evidence and exact release-date snapshots.

Missing exact snapshot: run the Phase III outcome-snapshot refresher.

Invalid no-look-ahead row: stop scoring and inspect lineage/cutoff identity.

Insufficient sample: preserve the documented insufficient-evidence state.

Surprising release association: inspect governed information sets and calendar;
do not rewrite temporal association as causal attribution.

## 13. Post-operation checks

```cmd
python scripts\verify_phase3_evaluation.py
python scripts\verify_phase2_release.py --require-tag
python scripts\verify_model1d_v038_release.py --require-tags
git status --short
```

Generated reports, exports, database files and backups must remain untracked.

## 14. Release discipline

Phase III v1.0.0 versions only the evaluation/decision-intelligence layer. It
does not increment Models 1A–1D.

The Phase III release tag may be created only after:

1. the Phase 3F hardening source commit is pushed;
2. `Phase III Evaluation Guard` succeeds on that source;
3. release metadata/validation record that successful source gate;
4. final release-closure tests pass;
5. the closure commit itself passes the Phase III guard.

Published Phase II and Model 1D tags must never be moved or recreated.
