# Model 2G — Pseudo-real-time Validation & Model Comparison

Model 2G begins from the closed Model 2F scenario-analysis workstream at
`c63ee4df92dd372f883feea4fc86eabae79ab358`, validated by Model 2 Bayesian VAR Guard run `35750342329`.

This workstream is the first Model 2 stage authorized to compare and select
among the six predeclared BVAR candidates. The selection rule is frozen before
the canonical development evidence is computed.

## Development inventory

The pseudo-real-time origin inventory uses every admissible Model 2B.2 origin.
There is no hand-selected evaluation start date.

The development inventory is frozen through origin quarter **2026Q1**.
Later prospective origins may not be appended to this development selection
sample.

For a forecast targeting quarter `q`, the outcome is the transformed row for
`q` from the **first common exact-vintage panel in which q is complete**. Later
revisions are not substituted for this outcome. Unresolved targets are excluded
rather than filled with future information.

## Compared models

All six Model 2C BVAR candidates are evaluated.

Three comparison-only benchmarks are also evaluated:

- univariate AR(4), estimated independently for each variable;
- classical VAR(4) with intercept;
- historical-mean forecasts for GDP growth and core PCE inflation, with
  random-walk forecasts for unemployment and the policy rate.

Benchmark predictive densities hold estimated parameters fixed and simulate
future innovations. BVAR predictive densities retain the Model 2D posterior
parameter uncertainty and future innovation uncertainty.

Benchmarks are not eligible for BVAR candidate selection.

## Metrics

Point forecast error is `forecast - outcome`. Reported point metrics are bias,
MAE and RMSE.

Density metrics are marginal log predictive density, empirical CRPS, central
50/80/95 percent coverage and the corresponding interval scores.

Log predictive density is estimated directly from predictive draws using a
Gaussian kernel with Silverman bandwidth. This is a simulation-based marginal
density estimate, not an analytic closed-form density.

All model comparisons use common resolved origin/variable/horizon cases.

## Candidate selection

Selection uses horizons 1, 2 and 4 only. Horizon 8 remains a diagnostic
evaluation horizon and does not determine the selected BVAR specification.

Each variable/horizon cell receives equal weight. Every primary cell must
contain at least eight resolved pseudo-real-time cases.

The deterministic order is:

1. highest mean log predictive density;
2. lowest mean CRPS;
3. lowest mean RMSE;
4. lexicographically smallest candidate ID.

The canonical run uses 5000 predictive draws per
model/origin with base seed 20260904. Per-model/per-origin seeds are
derived deterministically with SHA-256.

Running the canonical evaluation with `--freeze-evidence` creates
`MODEL2G_SELECTION_EVIDENCE.json`. Once created, the script refuses to
overwrite different evidence.

## Governance

The selected candidate is a frozen development decision only. Model 2G has no
production authority. Later prospective performance cannot automatically
retune, switch or replace the selected specification. Model 1D prospective
outcomes remain excluded, historical Model 1 outputs are not backfilled, and
frozen releases remain unchanged.
