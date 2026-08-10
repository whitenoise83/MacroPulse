# MacroPulse Internal Phase III Evaluation Release v1.0.0

## Roadmap context

This release is the **internal Forecast Evaluation & Decision Intelligence layer supporting the overall MacroPulse roadmap Phase I / Model 1**.

It is **not** the overall MacroPulse roadmap Phase III, which is reserved for Models 5–7 (Yield Curve, Financial Conditions & Credit, Regime Probabilities).

## Release scope

The release closes internal workstreams 3A–3F:

- 3A — bootstrap and evidence contract;
- 3B — production forecast evaluation ledger;
- 3C — accuracy, calibration, and drift monitoring;
- 3D — revision and scheduled-release impact analytics;
- 3E — deterministic decision-intelligence presentation;
- 3F — operational hardening, CI, runbook, and release closure.

The layer evaluates governed Models 1A–1C and presents evidence. It does not change their model specifications or execute them.

Model 1D remains development v0.3.8 prospective shadow research and is explicitly excluded from production evaluation/promotion authority.

## Immutable boundaries

The release preserves first-release outcome identity where defined, explicit outcome vintage, no-look-ahead scoring, separately labelled revised outcomes, monitoring-not-adaptation, descriptive scheduled-release association unless a causal design is governed, no automatic promotion/demotion, no governed forecast mutation, no Model 1D prospective backfill/tuning, and no generative AI in the governed evaluation core.

## Release ancestry

Base platform release:

```text
phase2-platform-v1.0.0
43395d889a76453706259a5095bd718337b55851
```

Phase 3F.1 closure-source commit:

```text
ac8af6425cdb79e1516614328b52ab761be1ffe4
```

That source commit passed `Phase III Evaluation Guard` run #1, run ID `31425130485`.

The final release closure is required to be exactly one commit after that source-gate commit.

## Release verification

Before the release tag exists:

```cmd
python scripts\verify_phase3_release.py
```

After the immutable tag is created:

```cmd
python scripts\verify_phase3_release.py --require-tag
```

Release tag:

```text
phase3-evaluation-v1.0.0
```

The tag must point at the final closure commit and must never be moved or recreated.

## Operational posture

This release freezes evaluation/presentation semantics at v1.0.0. Operational evidence may continue to accumulate in the database and generated reports, but release source semantics remain frozen until a separately governed future release is approved.

The release does not declare Model 1D production-ready. Its prospective evidence programme continues independently under frozen v0.3.8 rules.
