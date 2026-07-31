from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from macropulse.backtesting.metrics import (
    calculate_backtest_metrics,
    calculate_stage_metrics,
    calculate_stage_regime_metrics,
    clustered_coverage_test,
)
from macropulse.backtesting.production_selection import (
    ELIGIBLE_PRODUCTION_MODELS,
    ROBUST_STAGE_ADAPTIVE_MODEL_NAME,
    STABLE_STAGE_POLICY_NAME,
)
from macropulse.data.repository import MacroRepository
from macropulse.governance.audit import AuditCheck, audit_stage_backtest
from macropulse.governance.versioning import current_model_identity, load_governance_config
from macropulse.settings import settings


def _latest_id(repository: MacroRepository, table: str, id_column: str) -> str | None:
    frame = repository.query_df(
        f"SELECT {id_column} FROM {table} ORDER BY created_at DESC LIMIT 1"
    )
    return None if frame.empty else str(frame.iloc[0][id_column])


def _target_leakage_count(
    repository: MacroRepository,
    stage_results: pd.DataFrame,
    target_series: str,
) -> int:
    count = 0
    cutoffs = stage_results[["forecast_date", "target_period"]].drop_duplicates()
    for _, row in cutoffs.iterrows():
        period = pd.Period(str(row["target_period"]), freq="Q")
        snapshot = repository.query_df(
            """
            SELECT COUNT(*) AS observations
            FROM historical_snapshots
            WHERE as_of_date = ? AND series_id = ?
              AND observation_date BETWEEN ? AND ?
              AND value IS NOT NULL
            """,
            [
                pd.Timestamp(row["forecast_date"]).date(),
                target_series,
                period.start_time.date(),
                period.end_time.date(),
            ],
        )
        count += int(snapshot.iloc[0]["observations"])
    return count


def _future_observation_count(
    repository: MacroRepository,
    stage_results: pd.DataFrame,
) -> int:
    count = 0
    for forecast_date in pd.to_datetime(stage_results["forecast_date"]).dt.date.unique():
        frame = repository.query_df(
            """
            SELECT COUNT(*) AS observations
            FROM historical_snapshots
            WHERE as_of_date = ? AND observation_date > ? AND value IS NOT NULL
            """,
            [forecast_date, forecast_date],
        )
        count += int(frame.iloc[0]["observations"])
    return count


def _threshold_check(
    gate: str,
    name: str,
    observed: float,
    threshold_text: str,
    condition: bool,
    details: dict | None = None,
) -> AuditCheck:
    return AuditCheck(
        gate,
        name,
        "pass" if condition else "fail",
        f"{observed:.6g}" if np.isfinite(observed) else "not available",
        threshold_text,
        details or {},
    )


def _warning_check(
    gate: str,
    name: str,
    observed: str,
    details: dict | None = None,
) -> AuditCheck:
    return AuditCheck(gate, name, "warning", observed, "Review required", details or {})


def _parse_details(value: object) -> dict:
    try:
        return json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}


def _stable_policy_integrity(
    results: pd.DataFrame,
    diagnostics: pd.DataFrame,
    declared_policy: dict[str, str],
) -> AuditCheck:
    forecasts = results.loc[results["model_name"] == STABLE_STAGE_POLICY_NAME]
    diag_rows = diagnostics.loc[
        diagnostics["model_name"] == STABLE_STAGE_POLICY_NAME
    ] if not diagnostics.empty else pd.DataFrame()
    violations: list[dict] = []
    if len(forecasts) != len(diag_rows):
        violations.append(
            {
                "reason": "forecast/diagnostic row-count mismatch",
                "forecast_rows": int(len(forecasts)),
                "diagnostic_rows": int(len(diag_rows)),
            }
        )
    for _, row in diag_rows.iterrows():
        details = _parse_details(row.get("details_json"))
        stage = str(row.get("forecast_stage"))
        declared = str(declared_policy.get(stage, ""))
        selected = str(details.get("selected_component", ""))
        if selected not in ELIGIBLE_PRODUCTION_MODELS:
            violations.append({"forecast_stage": stage, "reason": "ineligible component", "selected": selected})
        if selected != declared and not details.get("fallback_used") and not details.get("fallback_reason"):
            violations.append(
                {
                    "forecast_stage": stage,
                    "reason": "selected component differs from declared policy without fallback",
                    "selected": selected,
                    "declared": declared,
                }
            )
    return AuditCheck(
        "Econometric validity",
        "Stable stage policy follows the pre-declared component map",
        "pass" if not violations else "fail",
        f"{len(violations)} violations",
        "0 violations",
        {"violations": violations[:50], "declared_policy": declared_policy},
    )


def _robust_selection_integrity(
    results: pd.DataFrame,
    diagnostics: pd.DataFrame,
    minimum_history: int,
) -> AuditCheck:
    forecasts = results.loc[results["model_name"] == ROBUST_STAGE_ADAPTIVE_MODEL_NAME]
    diag_rows = diagnostics.loc[
        diagnostics["model_name"] == ROBUST_STAGE_ADAPTIVE_MODEL_NAME
    ] if not diagnostics.empty else pd.DataFrame()
    violations: list[dict] = []
    if len(forecasts) != len(diag_rows):
        violations.append(
            {
                "reason": "forecast/diagnostic row-count mismatch",
                "forecast_rows": int(len(forecasts)),
                "diagnostic_rows": int(len(diag_rows)),
            }
        )
    for _, row in diag_rows.iterrows():
        details = _parse_details(row.get("details_json"))
        selected = details.get("selected_component")
        common_history = int(details.get("common_history", 0) or 0)
        switched = bool(details.get("switched", False))
        method = details.get("method")
        if selected not in ELIGIBLE_PRODUCTION_MODELS:
            violations.append(
                {
                    "forecast_date": str(row.get("forecast_date")),
                    "reason": "ineligible selected component",
                    "selected_component": selected,
                }
            )
            continue
        if switched and common_history < minimum_history:
            violations.append(
                {
                    "forecast_date": str(row.get("forecast_date")),
                    "reason": "switch used insufficient prior history",
                    "common_history": common_history,
                }
            )
        if switched:
            challenger_score = float(details.get("challenger_score", np.inf))
            required_score = float(details.get("required_challenger_score", -np.inf))
            if challenger_score > required_score:
                violations.append(
                    {
                        "forecast_date": str(row.get("forecast_date")),
                        "reason": "switch threshold not met",
                        "challenger_score": challenger_score,
                        "required_score": required_score,
                    }
                )
            if not bool(details.get("tail_guard_passed", False)):
                violations.append({"forecast_date": str(row.get("forecast_date")), "reason": "tail guard failed"})
            if not bool(details.get("maximum_error_guard_passed", False)):
                violations.append({"forecast_date": str(row.get("forecast_date")), "reason": "maximum-error guard failed"})
        if method not in {
            "stable_incumbent_fallback",
            "robust_prior_common_sample",
            "bridge_fallback_dfm_failure",
        }:
            violations.append(
                {
                    "forecast_date": str(row.get("forecast_date")),
                    "reason": "unknown selection method",
                    "method": method,
                }
            )
    return AuditCheck(
        "Econometric validity",
        "Robust shadow selector follows prior-only switching rules",
        "pass" if not violations else "fail",
        f"{len(violations)} violations",
        "0 violations",
        {
            "forecasts": int(len(forecasts)),
            "selection_diagnostics": int(len(diag_rows)),
            "violations": violations[:50],
        },
    )


def _selection_history(diagnostics: pd.DataFrame, model_name: str) -> pd.DataFrame:
    columns = [
        "forecast_stage",
        "forecast_date",
        "target_period",
        "selected_component",
        "method",
        "switched",
        "switch_reason",
    ]
    if diagnostics.empty:
        return pd.DataFrame(columns=columns)
    frame = diagnostics.loc[diagnostics["model_name"] == model_name].copy()
    if frame.empty:
        return pd.DataFrame(columns=columns)
    parsed = frame["details_json"].map(_parse_details)
    frame["selected_component"] = parsed.map(lambda item: item.get("selected_component", "Unknown"))
    frame["method"] = parsed.map(lambda item: item.get("method", "Unknown"))
    frame["switched"] = parsed.map(lambda item: bool(item.get("switched", False)))
    frame["switch_reason"] = parsed.map(lambda item: item.get("switch_reason", ""))
    return frame[columns].sort_values(["forecast_stage", "forecast_date"])


def _selection_distribution(diagnostics: pd.DataFrame, model_name: str) -> pd.DataFrame:
    history = _selection_history(diagnostics, model_name)
    if history.empty:
        return pd.DataFrame(columns=["forecast_stage", "selected_component", "forecasts"])
    return (
        history.groupby(["forecast_stage", "selected_component"])
        .size()
        .rename("forecasts")
        .reset_index()
        .sort_values(["forecast_stage", "forecasts"], ascending=[True, False])
    )


def _selection_stability(diagnostics: pd.DataFrame) -> pd.DataFrame:
    history = _selection_history(diagnostics, ROBUST_STAGE_ADAPTIVE_MODEL_NAME)
    rows: list[dict] = []
    for stage, group in history.groupby("forecast_stage", sort=False):
        group = group.sort_values("forecast_date").copy()
        selected = group["selected_component"].astype(str).tolist()
        switches = sum(left != right for left, right in zip(selected, selected[1:]))
        run_lengths: list[int] = []
        if selected:
            length = 1
            for left, right in zip(selected, selected[1:]):
                if left == right:
                    length += 1
                else:
                    run_lengths.append(length)
                    length = 1
            run_lengths.append(length)
        rows.append(
            {
                "forecast_stage": stage,
                "forecasts": int(len(group)),
                "switches": int(switches),
                "switch_rate": float(switches / max(len(group) - 1, 1)),
                "average_model_duration": float(np.mean(run_lengths)) if run_lengths else float("nan"),
                "minimum_model_duration": int(min(run_lengths)) if run_lengths else 0,
            }
        )
    return pd.DataFrame(rows)


def _accuracy_eligible_tail_benchmark(
    stage_frame: pd.DataFrame,
    production_model: str,
    static_names: list[str],
    rmse_limit: float,
    mae_limit: float,
    max_error_limit: float,
) -> dict:
    """Build a coherent upper-tail benchmark from accuracy-competitive models.

    A model is not allowed to become the p90 comparator solely because it has a
    low 90th-percentile error while being materially worse on RMSE, MAE, or the
    maximum error. This avoids constructing a different, unattainable
    "Frankenstein benchmark" for every loss statistic.
    """
    static = stage_frame.loc[stage_frame.index.intersection(static_names)].copy()
    if production_model not in stage_frame.index or static.empty:
        return {
            "eligible_models": [],
            "excluded_models": {},
            "best_p90": float("nan"),
            "best_p90_model": None,
            "production_p90": float("nan"),
            "p90_ratio": float("inf"),
        }

    best_rmse = float(static["rmse"].min())
    best_mae = float(static["mae"].min())
    best_max = float(static["max_abs_error"].min())

    rmse_ratio = static["rmse"].astype(float) / best_rmse
    mae_ratio = static["mae"].astype(float) / best_mae
    max_ratio = static["max_abs_error"].astype(float) / best_max
    eligible_mask = (
        (rmse_ratio <= rmse_limit)
        & (mae_ratio <= mae_limit)
        & (max_ratio <= max_error_limit)
    )
    eligible = static.loc[eligible_mask].copy()

    # The production component should normally be eligible. Retaining it as a
    # final fallback prevents an empty comparator set because of rounding or a
    # deliberately strict configuration.
    if eligible.empty:
        production_component = stage_frame.loc[[production_model]].copy()
        eligible = production_component

    best_p90_model = str(eligible["p90_abs_error"].astype(float).idxmin())
    best_p90 = float(eligible.loc[best_p90_model, "p90_abs_error"])
    production_p90 = float(stage_frame.loc[production_model, "p90_abs_error"])
    p90_ratio = production_p90 / best_p90 if best_p90 > 0 else float("inf")

    excluded: dict[str, dict[str, float]] = {}
    for model_name in static.index[~eligible_mask]:
        excluded[str(model_name)] = {
            "rmse_ratio": float(rmse_ratio.loc[model_name]),
            "mae_ratio": float(mae_ratio.loc[model_name]),
            "max_error_ratio": float(max_ratio.loc[model_name]),
        }

    return {
        "eligible_models": [str(name) for name in eligible.index],
        "excluded_models": excluded,
        "best_p90": best_p90,
        "best_p90_model": best_p90_model,
        "production_p90": production_p90,
        "p90_ratio": p90_ratio,
        "eligibility_limits": {
            "rmse_ratio": rmse_limit,
            "mae_ratio": mae_limit,
            "max_error_ratio": max_error_limit,
        },
    }


def _render_markdown_table(frame: pd.DataFrame, columns: list[str], decimals: int = 4) -> list[str]:
    if frame.empty:
        return ["No results were available."]
    selected = frame[columns].copy()
    for column in columns:
        if pd.api.types.is_numeric_dtype(selected[column]):
            selected[column] = selected[column].round(decimals)
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for _, row in selected.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return lines


def _render_report(
    identity: dict,
    validation_id: str,
    status: str,
    stage_backtest_id: str,
    checks: list[AuditCheck],
    stage_metrics: pd.DataFrame,
    regime_metrics: pd.DataFrame,
    stable_distribution: pd.DataFrame,
    robust_distribution: pd.DataFrame,
    stability: pd.DataFrame,
    champion: str,
    output_path: Path,
) -> None:
    passed = sum(check.status == "pass" for check in checks)
    failed = sum(check.status == "fail" for check in checks)
    warnings = sum(check.status == "warning" for check in checks)
    champion_metrics = stage_metrics.loc[stage_metrics["model_name"] == champion].copy()
    robust_metrics = stage_metrics.loc[
        stage_metrics["model_name"] == ROBUST_STAGE_ADAPTIVE_MODEL_NAME
    ].copy()
    champion_regimes = regime_metrics.loc[regime_metrics["model_name"] == champion].copy()

    lines = [
        f"# {identity['display_name']} - Model Freeze Validation Report",
        "",
        f"- Validation ID: `{validation_id}`",
        f"- Model version: `{identity['model_version']}`",
        f"- Lifecycle status: `{identity['lifecycle_status']}`",
        f"- Stage backtest: `{stage_backtest_id}`",
        f"- Production policy: `{champion}`",
        f"- Shadow challenger: `{ROBUST_STAGE_ADAPTIVE_MODEL_NAME}`",
        f"- Overall status: **{status.upper()}**",
        f"- Checks: {passed} passed, {failed} failed, {warnings} warnings",
        f"- Configuration hash: `{identity['config_hash']}`",
        f"- Code hash: `{identity['code_hash']}`",
        "",
        "## Validation checks",
        "",
        "| Gate | Check | Status | Observed | Threshold |",
        "|---|---|---:|---:|---:|",
    ]
    for check in checks:
        lines.append(
            f"| {check.gate_name} | {check.check_name} | {check.status.upper()} | "
            f"{check.observed_value} | {check.threshold} |"
        )

    lines.extend(["", "## Stable production policy performance", ""])
    lines.extend(
        _render_markdown_table(
            champion_metrics,
            [
                "forecast_stage",
                "observations",
                "rmse",
                "trimmed_rmse_10",
                "mae",
                "p90_abs_error",
                "max_abs_error",
                "interval_coverage",
                "average_interval_width",
                "interval_score_80",
            ],
        )
    )
    lines.extend(["", "## Robust adaptive shadow performance", ""])
    lines.extend(
        _render_markdown_table(
            robust_metrics,
            [
                "forecast_stage",
                "observations",
                "rmse",
                "mae",
                "p90_abs_error",
                "max_abs_error",
                "interval_coverage",
            ],
        )
    )
    lines.extend(["", "## Stable policy components", ""])
    lines.extend(_render_markdown_table(stable_distribution, ["forecast_stage", "selected_component", "forecasts"], decimals=0))
    lines.extend(["", "## Robust adaptive selections", ""])
    lines.extend(_render_markdown_table(robust_distribution, ["forecast_stage", "selected_component", "forecasts"], decimals=0))
    lines.extend(["", "## Robust selector stability", ""])
    lines.extend(
        _render_markdown_table(
            stability,
            ["forecast_stage", "forecasts", "switches", "switch_rate", "average_model_duration", "minimum_model_duration"],
        )
    )
    lines.extend(["", "## Production policy regime performance", ""])
    lines.extend(
        _render_markdown_table(
            champion_regimes,
            [
                "forecast_stage",
                "sample",
                "observations",
                "rmse",
                "trimmed_rmse_10",
                "mae",
                "p90_abs_error",
                "max_abs_error",
                "interval_coverage",
                "average_interval_width",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Freeze decision rule",
            "",
            "The Stable Stage Policy is the approved Model 1A v1.0.0 production policy. The robust adaptive policy remains a shadow challenger until live evidence supports a separately validated promotion.",
            "",
            "This report validates Model 1A (GDP). Inflation and labour-market nowcasts remain Model 1B and Model 1C work.",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_model_validation(
    repository: MacroRepository | None = None,
    stage_backtest_id: str | None = None,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    identity = current_model_identity().as_dict()
    governance = load_governance_config()
    thresholds = governance.get("validation", {})
    policy = governance.get("production_policy", {})
    target_series = governance["model"].get("target_series", "GDPC1")
    champion = str(governance["model"].get("champion_model", STABLE_STAGE_POLICY_NAME))

    validation_source_version = str(
        governance.get("model", {}).get(
            "validation_source_version", identity["model_version"]
        )
    )
    if stage_backtest_id is None:
        latest_stage = repository.query_df(
            """
            SELECT stage_backtest_id
            FROM stage_backtest_runs
            WHERE model_version = ? AND status IN ('success', 'partial')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [validation_source_version],
        )
        stage_backtest_id = (
            None if latest_stage.empty else str(latest_stage.iloc[0]["stage_backtest_id"])
        )
    if stage_backtest_id is None:
        raise RuntimeError(
            f"No staged backtest exists for validated source version "
            f"{validation_source_version}."
        )

    stage_run = repository.query_df(
        "SELECT model_version FROM stage_backtest_runs WHERE stage_backtest_id = ?",
        [stage_backtest_id],
    )
    if stage_run.empty:
        raise RuntimeError(f"Staged backtest {stage_backtest_id} is not registered.")
    staged_version = str(stage_run.iloc[0]["model_version"])
    if staged_version != validation_source_version:
        raise RuntimeError(
            f"Selected staged backtest is version {staged_version}, but the approved "
            f"validation source version is {validation_source_version}."
        )

    results = repository.query_df(
        "SELECT * FROM stage_backtest_results WHERE stage_backtest_id = ? ORDER BY forecast_date, forecast_stage, model_name",
        [stage_backtest_id],
    )
    diagnostics = repository.query_df(
        "SELECT * FROM stage_backtest_diagnostics WHERE stage_backtest_id = ? ORDER BY forecast_date, forecast_stage, model_name",
        [stage_backtest_id],
    )
    if results.empty:
        raise RuntimeError(f"Staged backtest {stage_backtest_id} contains no results.")

    leakage = _target_leakage_count(repository, results, target_series)
    future_observations = _future_observation_count(repository, results)
    checks = audit_stage_backtest(
        results,
        diagnostics,
        target_snapshot_leakage_count=leakage,
        future_observation_count=future_observations,
    )
    metrics = calculate_backtest_metrics(results)
    stage_metrics = calculate_stage_metrics(results)
    regime_metrics = calculate_stage_regime_metrics(results)
    stable_distribution = _selection_distribution(diagnostics, STABLE_STAGE_POLICY_NAME)
    robust_distribution = _selection_distribution(diagnostics, ROBUST_STAGE_ADAPTIVE_MODEL_NAME)
    stability = _selection_stability(diagnostics)

    checks.append(
        _stable_policy_integrity(
            results,
            diagnostics,
            declared_policy={str(k): str(v) for k, v in policy.get("stable_stage_policy", {}).items()},
        )
    )
    checks.append(
        _robust_selection_integrity(
            results,
            diagnostics,
            minimum_history=int(policy.get("selection_min_history", 20)),
        )
    )

    maximum_switches = int(thresholds.get("robust_max_switches_per_stage", 6))
    observed_switches = int(stability["switches"].max()) if not stability.empty else 0
    checks.append(
        _threshold_check(
            "Econometric validity",
            "Robust shadow selector has acceptable switching stability",
            float(observed_switches),
            f"<= {maximum_switches} switches per stage",
            observed_switches <= maximum_switches,
            {"stage_stability": stability.to_dict(orient="records")},
        )
    )

    minimum_quarters = int(thresholds.get("minimum_evaluated_quarters", 20))
    champion_rows = results.loc[results["model_name"] == champion]
    stage_quarter_counts = (
        champion_rows.groupby("forecast_stage")["target_period"].nunique()
        if not champion_rows.empty
        else pd.Series(dtype=int)
    )
    minimum_stage_quarters = int(stage_quarter_counts.min()) if not stage_quarter_counts.empty else 0
    checks.append(
        _threshold_check(
            "Econometric validity",
            "Minimum evaluated quarters at every forecast stage",
            float(minimum_stage_quarters),
            f">= {minimum_quarters}",
            minimum_stage_quarters >= minimum_quarters,
            {"stage_counts": {str(k): int(v) for k, v in stage_quarter_counts.items()}},
        )
    )

    metric_map = metrics.set_index("model_name") if not metrics.empty else pd.DataFrame()
    if champion in metric_map.index and "Bridge Ridge" in metric_map.index:
        champion_rmse = float(metric_map.loc[champion, "rmse"])
        bridge_rmse = float(metric_map.loc["Bridge Ridge", "rmse"])
        ratio = champion_rmse / bridge_rmse if bridge_rmse > 0 else float("inf")
        maximum_ratio = float(thresholds.get("champion_max_rmse_ratio_to_bridge", 1.02))
        checks.append(
            _threshold_check(
                "Econometric validity",
                "Production RMSE relative to Bridge benchmark",
                ratio,
                f"<= {maximum_ratio:.3f}",
                ratio <= maximum_ratio,
                {"production_rmse": champion_rmse, "bridge_rmse": bridge_rmse},
            )
        )

        interval_score_ratio = float(metric_map.loc[champion, "interval_score_80"]) / float(
            metric_map.loc["Bridge Ridge", "interval_score_80"]
        )
        maximum_interval_score_ratio = float(thresholds.get("maximum_interval_score_ratio_to_bridge", 1.10))
        checks.append(
            _threshold_check(
                "Uncertainty calibration",
                "Production interval score relative to Bridge benchmark",
                interval_score_ratio,
                f"<= {maximum_interval_score_ratio:.3f}",
                interval_score_ratio <= maximum_interval_score_ratio,
                {},
            )
        )

        target_coverage = float(thresholds.get("interval_target_coverage", 0.80))
        significance = float(thresholds.get("interval_test_significance", 0.05))
        overall_coverage = clustered_coverage_test(
            results,
            model_name=champion,
            target_coverage=target_coverage,
            bootstrap_samples=int(thresholds.get("clustered_coverage_bootstrap_samples", 5000)),
        )
        checks.append(
            AuditCheck(
                "Uncertainty calibration",
                "Production coverage is cluster-consistent with the target",
                "pass" if float(overall_coverage["p_value"]) >= significance else "warning",
                json.dumps(
                    {
                        "coverage": round(float(overall_coverage["coverage"]), 4),
                        "cluster_bootstrap_p_value": round(float(overall_coverage["p_value"]), 6),
                        "bootstrap_95_ci": [
                            round(float(overall_coverage["ci_lower"]), 4),
                            round(float(overall_coverage["ci_upper"]), 4),
                        ],
                        "quarters": int(overall_coverage["clusters"]),
                        "forecasts": int(overall_coverage["forecasts"]),
                    }
                ),
                f"target-quarter clustered bootstrap p-value >= {significance:.2f}",
                overall_coverage,
            )
        )

        static_names = [name for name in ELIGIBLE_PRODUCTION_MODELS]
        ratio_details: dict[str, dict] = {}
        rmse_ratios: list[float] = []
        mae_ratios: list[float] = []
        p90_ratios: list[float] = []
        max_error_ratios: list[float] = []
        stage_coverage_tests: dict[str, dict] = {}
        for stage in stage_metrics["forecast_stage"].dropna().unique():
            stage_frame = stage_metrics.loc[stage_metrics["forecast_stage"] == stage].set_index("model_name")
            static = stage_frame.loc[stage_frame.index.intersection(static_names)]
            if champion not in stage_frame.index or static.empty:
                continue
            production = stage_frame.loc[champion]
            best_rmse = float(static["rmse"].min())
            best_mae = float(static["mae"].min())
            best_max = float(static["max_abs_error"].min())
            stage_rmse_ratio = float(production["rmse"]) / best_rmse
            stage_mae_ratio = float(production["mae"]) / best_mae
            stage_max_ratio = float(production["max_abs_error"]) / best_max
            tail_benchmark = _accuracy_eligible_tail_benchmark(
                stage_frame,
                champion,
                static_names,
                rmse_limit=float(thresholds.get("champion_max_stage_rmse_ratio_to_best_static", 1.10)),
                mae_limit=float(thresholds.get("champion_max_stage_mae_ratio_to_best_static", 1.10)),
                max_error_limit=float(thresholds.get("champion_max_stage_max_error_ratio_to_best_static", 1.25)),
            )
            stage_p90_ratio = float(tail_benchmark["p90_ratio"])
            rmse_ratios.append(stage_rmse_ratio)
            mae_ratios.append(stage_mae_ratio)
            p90_ratios.append(stage_p90_ratio)
            max_error_ratios.append(stage_max_ratio)
            ratio_details[str(stage)] = {
                "rmse_ratio": stage_rmse_ratio,
                "mae_ratio": stage_mae_ratio,
                "p90_ratio": stage_p90_ratio,
                "max_error_ratio": stage_max_ratio,
                "best_rmse_model": str(static["rmse"].idxmin()),
                "best_mae_model": str(static["mae"].idxmin()),
                "best_p90_model": str(tail_benchmark["best_p90_model"]),
                "best_max_error_model": str(static["max_abs_error"].idxmin()),
                "tail_benchmark": tail_benchmark,
            }
            stage_coverage_tests[str(stage)] = {
                "coverage": float(production["interval_coverage"]),
                "p_value": float(production["coverage_p_value"]),
            }

        rmse_limit = float(thresholds.get("champion_max_stage_rmse_ratio_to_best_static", 1.10))
        mae_limit = float(thresholds.get("champion_max_stage_mae_ratio_to_best_static", 1.10))
        p90_limit = float(thresholds.get("champion_max_stage_p90_ratio_to_best_static", 1.20))
        max_limit = float(thresholds.get("champion_max_stage_max_error_ratio_to_best_static", 1.25))
        checks.extend(
            [
                _threshold_check(
                    "Econometric validity",
                    "Production RMSE is competitive with the best static model at every stage",
                    max(rmse_ratios) if rmse_ratios else float("inf"),
                    f"<= {rmse_limit:.3f}",
                    bool(rmse_ratios) and max(rmse_ratios) <= rmse_limit,
                    ratio_details,
                ),
                _threshold_check(
                    "Econometric validity",
                    "Production MAE is competitive with the best static model at every stage",
                    max(mae_ratios) if mae_ratios else float("inf"),
                    f"<= {mae_limit:.3f}",
                    bool(mae_ratios) and max(mae_ratios) <= mae_limit,
                    ratio_details,
                ),
                _threshold_check(
                    "Econometric validity",
                    "Production upper-tail error is competitive among accuracy-eligible static models at every stage",
                    max(p90_ratios) if p90_ratios else float("inf"),
                    f"<= {p90_limit:.3f}",
                    bool(p90_ratios) and max(p90_ratios) <= p90_limit,
                    ratio_details,
                ),
                _threshold_check(
                    "Econometric validity",
                    "Production maximum error is not materially worse at any stage",
                    max(max_error_ratios) if max_error_ratios else float("inf"),
                    f"<= {max_limit:.3f}",
                    bool(max_error_ratios) and max(max_error_ratios) <= max_limit,
                    ratio_details,
                ),
            ]
        )
        stage_coverage_ok = bool(stage_coverage_tests) and all(
            values["p_value"] >= significance for values in stage_coverage_tests.values()
        )
        checks.append(
            AuditCheck(
                "Uncertainty calibration",
                "Production coverage is statistically acceptable at every stage",
                "pass" if stage_coverage_ok else "warning",
                json.dumps(
                    {
                        key: {
                            "coverage": round(value["coverage"], 4),
                            "p_value": round(value["p_value"], 6),
                        }
                        for key, value in stage_coverage_tests.items()
                    }
                ),
                f"exact stage-level binomial p-value >= {significance:.2f}",
                {"stage_coverage_tests": stage_coverage_tests},
            )
        )
    else:
        checks.append(
            AuditCheck(
                "Econometric validity",
                "Production and Bridge metrics are available",
                "fail",
                "missing model metrics",
                "both required",
                {},
            )
        )

    required_samples = {
        "Full sample",
        "Pre-pandemic (through 2019Q4)",
        "Pandemic (2020Q1–2021Q2)",
        "Post-pandemic (from 2021Q3)",
        "Last 20 quarters",
    }
    champion_regimes = regime_metrics.loc[regime_metrics["model_name"] == champion]
    missing_regimes: dict[str, list[str]] = {}
    for stage in sorted(results["forecast_stage"].dropna().unique()):
        observed = set(
            champion_regimes.loc[champion_regimes["forecast_stage"] == stage, "sample"].astype(str)
        )
        missing = sorted(required_samples.difference(observed))
        if missing:
            missing_regimes[str(stage)] = missing
    checks.append(
        AuditCheck(
            "Econometric validity",
            "Production performance is reported for all declared economic regimes",
            "pass" if not missing_regimes else "fail",
            f"{len(missing_regimes)} stages with missing regime results",
            "0 missing stage/regime combinations",
            {"missing": missing_regimes},
        )
    )

    attempted = diagnostics.loc[diagnostics["model_name"] == "Dynamic Factor Model"]
    failures = int((attempted["status"] != "success").sum()) if not attempted.empty else 0
    failure_rate = failures / len(attempted) if len(attempted) else 1.0
    maximum_failure = float(thresholds.get("maximum_dfm_failure_rate", 0.10))
    checks.append(
        _threshold_check(
            "Operational reliability",
            "DFM estimation failure rate",
            failure_rate,
            f"<= {maximum_failure:.0%}",
            failure_rate <= maximum_failure,
            {"attempts": int(len(attempted)), "failures": failures},
        )
    )

    news = repository.query_df(
        """
        WITH contribution_sums AS (
            SELECT decomposition_id, COALESCE(SUM(impact), 0.0) AS contribution_sum
            FROM nowcast_news_contributions
            GROUP BY decomposition_id
        )
        SELECT news.decomposition_id, news.status, news.total_change,
               news.residual_interaction,
               COALESCE(contribution_sums.contribution_sum, 0.0) AS contribution_sum,
               news.total_change - COALESCE(contribution_sums.contribution_sum, 0.0) AS arithmetic_gap
        FROM nowcast_news_runs AS news
        LEFT JOIN contribution_sums USING (decomposition_id)
        ORDER BY news.created_at DESC
        LIMIT 20
        """
    )
    if news.empty:
        checks.append(_warning_check("Operational reliability", "Live news decompositions have been observed", "no governed live decomposition history"))
    else:
        successful = news.loc[news["status"] == "success"].copy()
        arithmetic_tolerance = float(thresholds.get("maximum_news_arithmetic_gap", 1e-6))
        maximum_arithmetic_gap = float(successful["arithmetic_gap"].abs().max()) if not successful.empty else float("inf")
        checks.append(
            _threshold_check(
                "Operational reliability",
                "News decomposition arithmetic closes",
                maximum_arithmetic_gap,
                f"<= {arithmetic_tolerance}",
                maximum_arithmetic_gap <= arithmetic_tolerance,
                {"successful_runs": int(len(successful)), "observed_runs": int(len(news))},
            )
        )
        residual_tolerance = float(thresholds.get("maximum_news_residual_interaction", 0.01))
        maximum_residual = float(successful["residual_interaction"].abs().max()) if not successful.empty else float("inf")
        checks.append(
            _threshold_check(
                "Operational reliability",
                "News attribution residual is immaterial",
                maximum_residual,
                f"<= {residual_tolerance} pp",
                maximum_residual <= residual_tolerance,
                {"successful_runs": int(len(successful)), "observed_runs": int(len(news))},
            )
        )

    registry_rows = repository.query_df(
        "SELECT COUNT(*) AS records FROM model_registry WHERE model_id = ? AND model_version = ?",
        [identity["model_id"], identity["model_version"]],
    )
    registered = int(registry_rows.iloc[0]["records"]) > 0
    checks.append(
        AuditCheck(
            "Reproducibility",
            "Model version is registered",
            "pass" if registered else "fail",
            "registered" if registered else "not registered",
            "registered",
            {},
        )
    )
    forecast_rows = repository.query_df(
        "SELECT COUNT(*) AS records FROM forecast_registry WHERE model_id = ? AND model_version = ?",
        [identity["model_id"], identity["model_version"]],
    )
    live_registered = int(forecast_rows.iloc[0]["records"]) > 0
    checks.append(
        AuditCheck(
            "Reproducibility",
            "At least one live forecast has a governance signature",
            "pass" if live_registered else "warning",
            "available" if live_registered else "run the governed live nowcast for v1.0.0",
            "at least one record",
            {},
        )
    )

    failed = [check for check in checks if check.status == "fail"]
    warnings = [check for check in checks if check.status == "warning"]
    status = "fail" if failed else ("conditional" if warnings else "pass")
    validation_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).replace(tzinfo=None)
    report_path = settings.validation_report_dir / f"model1a_freeze_validation_{created_at.strftime('%Y%m%d_%H%M%S')}.md"
    _render_report(
        identity,
        validation_id,
        status,
        stage_backtest_id,
        checks,
        stage_metrics,
        regime_metrics,
        stable_distribution,
        robust_distribution,
        stability,
        champion,
        report_path,
    )

    check_rows = []
    for check in checks:
        row = check.as_dict()
        row.update({"validation_id": validation_id, "created_at": created_at})
        check_rows.append(row)
    checks_frame = pd.DataFrame(check_rows)[
        [
            "validation_id",
            "gate_name",
            "check_name",
            "status",
            "observed_value",
            "threshold",
            "details_json",
            "created_at",
        ]
    ]
    summary = {
        "status": status,
        "passed": sum(check.status == "pass" for check in checks),
        "failed": len(failed),
        "warnings": len(warnings),
        "stage_backtest_id": stage_backtest_id,
        "report_path": str(report_path),
    }
    run_frame = pd.DataFrame(
        [
            {
                "validation_id": validation_id,
                "created_at": created_at,
                "model_id": identity["model_id"],
                "model_version": identity["model_version"],
                "stage_backtest_id": stage_backtest_id,
                "quarter_backtest_id": _latest_id(repository, "backtest_runs", "backtest_id"),
                "status": status,
                "passed_gates": summary["passed"],
                "total_gates": len(checks),
                "report_path": str(report_path.relative_to(settings.project_root)),
                "summary_json": json.dumps(summary),
                "notes": (
                    "Automated Model 1A v1.0.0 production verification using the approved v0.6.1 staged validation evidence. The Stable Stage Policy is production; the robust adaptive policy remains a shadow challenger."
                ),
            }
        ]
    )
    repository.save_validation_outputs(run_frame, checks_frame)
    return {
        "validation_id": validation_id,
        "status": status,
        "checks": pd.DataFrame([check.as_dict() for check in checks]),
        "stage_metrics": stage_metrics,
        "regime_metrics": regime_metrics,
        "selection_distribution": robust_distribution,
        "stable_distribution": stable_distribution,
        "selection_stability": stability,
        "report_path": report_path,
        "summary": summary,
    }
