from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Mapping

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.settings import settings


SELECTED_INTERVAL_METHOD = "exp_weighted_q80"


STABLE_POLICY: dict[str, dict[str, str]] = {
    "CPIAUCSL": {
        "month_open": "Inflation Ridge-AR Ensemble",
        "mid_month": "Inflation Ridge-AR Ensemble",
        "month_end": "Inflation Ridge-AR Ensemble",
        "pre_release": "Inflation Ridge-AR Ensemble",
    },
    "CPILFESL": {
        "month_open": "Inflation 12-Month Mean",
        "mid_month": "Inflation Ridge-AR Ensemble",
        "month_end": "Inflation Ridge-AR Ensemble",
        "pre_release": "Inflation Ridge-AR Ensemble",
    },
    "PCEPI": {
        "month_open": "Inflation Bridge Ridge",
        "mid_month": "Inflation Bridge Ridge",
        "month_end": "Inflation Bridge Ridge",
        "pre_release": "Inflation Bridge Ridge",
    },
    "PCEPILFE": {
        "month_open": "Inflation Bridge Ridge",
        "mid_month": "Inflation Ridge-AR Ensemble",
        "month_end": "Inflation Ridge-AR Ensemble",
        "pre_release": "Inflation Ridge-AR Ensemble",
    },
}


@dataclass(frozen=True)
class ShadowSelectorConfig:
    minimum_prior_errors: int = 24
    rolling_window: int = 36
    switch_hurdle: float = 0.02
    mae_guard: float = 1.05
    tail_guard: float = 1.10
    max_error_guard: float = 1.15


def policy_model(target_series: str, forecast_stage: str) -> str:
    try:
        return STABLE_POLICY[target_series][forecast_stage]
    except KeyError as exc:
        raise ValueError(
            f"No Model 1B stable-policy component is declared for "
            f"{target_series} / {forecast_stage}."
        ) from exc


def _metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    errors = pd.to_numeric(frame["error"], errors="coerce").dropna().astype(float)
    if errors.empty:
        return {}
    absolute = errors.abs()
    return {
        "observations": int(len(errors)),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "mae": float(absolute.mean()),
        "bias": float(errors.mean()),
        "median_ae": float(absolute.median()),
        "p90_abs_error": float(absolute.quantile(0.90)),
        "max_abs_error": float(absolute.max()),
    }


def robust_score(metrics: Mapping[str, float | int]) -> float:
    """Accuracy score used only by the prior-only shadow challenger.

    All terms are measured in annualised percentage points, so the weighted sum
    remains interpretable. RMSE dominates, while MAE, tail error and bias reduce
    the chance that a tiny RMSE advantage drives unstable switching.
    """
    return float(
        0.55 * float(metrics["rmse"])
        + 0.25 * float(metrics["mae"])
        + 0.15 * float(metrics["p90_abs_error"])
        + 0.05 * abs(float(metrics["bias"]))
    )


def select_fixed_policy(results: pd.DataFrame) -> pd.DataFrame:
    required = {"target_series", "forecast_stage", "target_period", "model_name"}
    missing = sorted(required.difference(results.columns))
    if missing:
        raise ValueError(f"Vintage results are missing required columns: {missing}")
    selected = results.copy()
    selected["policy_model"] = [
        policy_model(str(target), str(stage))
        for target, stage in zip(selected["target_series"], selected["forecast_stage"])
    ]
    selected = selected.loc[selected["model_name"] == selected["policy_model"]].copy()
    selected["selection_policy"] = "stable_candidate"
    return selected.sort_values(["target_series", "forecast_stage", "target_period"])


def _candidate_metrics(prior: pd.DataFrame, window: int) -> dict[str, dict[str, float | int]]:
    ordered = prior.copy()
    ordered["_period"] = pd.PeriodIndex(ordered["target_period"], freq="M")
    periods = sorted(ordered["_period"].unique())[-window:]
    ordered = ordered.loc[ordered["_period"].isin(periods)]
    return {
        str(model): _metrics(frame)
        for model, frame in ordered.groupby("model_name")
        if not frame.empty
    }


def select_prior_only_shadow(
    results: pd.DataFrame,
    config: ShadowSelectorConfig | None = None,
) -> pd.DataFrame:
    config = config or ShadowSelectorConfig()
    rows: list[dict] = []
    work = results.copy()
    work["_period"] = pd.PeriodIndex(work["target_period"], freq="M")
    work = work.sort_values(["target_series", "forecast_stage", "_period", "model_name"])

    for (target, stage), group in work.groupby(["target_series", "forecast_stage"]):
        periods = sorted(group["_period"].unique())
        incumbent = policy_model(str(target), str(stage))
        previous_period: pd.Period | None = None
        switch_count = 0
        for period in periods:
            prior = group.loc[group["_period"] < period]
            common_prior_periods = int(prior["_period"].nunique())
            metrics_by_model: dict[str, dict[str, float | int]] = {}
            selected = incumbent
            reason = "insufficient prior forecast errors"

            if common_prior_periods >= config.minimum_prior_errors:
                metrics_by_model = _candidate_metrics(prior, config.rolling_window)
                incumbent_metrics = metrics_by_model.get(incumbent)
                if incumbent_metrics:
                    incumbent_score = robust_score(incumbent_metrics)
                    eligible: list[tuple[float, str]] = []
                    for model, metrics in metrics_by_model.items():
                        if int(metrics.get("observations", 0)) < config.minimum_prior_errors:
                            continue
                        score = robust_score(metrics)
                        if model == incumbent:
                            eligible.append((score, model))
                            continue
                        accuracy_gate = score <= incumbent_score * (1.0 - config.switch_hurdle)
                        mae_gate = float(metrics["mae"]) <= float(incumbent_metrics["mae"]) * config.mae_guard
                        tail_gate = float(metrics["p90_abs_error"]) <= float(incumbent_metrics["p90_abs_error"]) * config.tail_guard
                        max_gate = float(metrics["max_abs_error"]) <= float(incumbent_metrics["max_abs_error"]) * config.max_error_guard
                        if accuracy_gate and mae_gate and tail_gate and max_gate:
                            eligible.append((score, model))
                    if eligible:
                        eligible.sort(key=lambda item: (item[0], item[1]))
                        selected = eligible[0][1]
                        reason = "prior-only robust score and risk guards"
                    else:
                        reason = "no challenger cleared the switch hurdle and risk guards"

            current = group.loc[(group["_period"] == period) & (group["model_name"] == selected)]
            if current.empty:
                raise RuntimeError(f"Selected model {selected} is missing for {target} {stage} {period}.")
            row = current.iloc[0].to_dict()
            changed = selected != incumbent
            if changed:
                switch_count += 1
            row.update(
                {
                    "selection_policy": "prior_only_shadow",
                    "selected_model": selected,
                    "previous_model": incumbent,
                    "selection_changed": changed,
                    "selection_reason": reason,
                    "prior_period_count": common_prior_periods,
                    "selection_cutoff_period": str(previous_period) if previous_period else None,
                    "selection_metrics_json": json.dumps(metrics_by_model, sort_keys=True, default=str),
                    "cumulative_switch_count": switch_count,
                }
            )
            rows.append(row)
            incumbent = selected
            previous_period = period

    output = pd.DataFrame(rows)
    if not output.empty:
        output = output.drop(columns=[column for column in ["_period"] if column in output])
    return output.sort_values(["target_series", "forecast_stage", "target_period"])


def summarise_forecasts(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for (target, stage), group in frame.groupby(["target_series", "forecast_stage"]):
        metrics = _metrics(group)
        rows.append(
            {
                "target_series": target,
                "forecast_stage": stage,
                **metrics,
                "model_name": (
                    str(group["model_name"].iloc[0])
                    if group["model_name"].nunique() == 1
                    else "Adaptive shadow"
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["target_series", "forecast_stage"])


def _quantile(values: np.ndarray, probability: float) -> float:
    try:
        return float(np.quantile(values, probability, method="linear"))
    except TypeError:
        return float(np.quantile(values, probability, interpolation="linear"))


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, probability: float) -> float:
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights)
    cutoff = probability * cumulative[-1]
    return float(values[np.searchsorted(cumulative, cutoff, side="left")])


def _interval_score(actual: float, lower: float, upper: float, alpha: float = 0.20) -> float:
    score = upper - lower
    if actual < lower:
        score += (2.0 / alpha) * (lower - actual)
    elif actual > upper:
        score += (2.0 / alpha) * (actual - upper)
    return float(score)


def interval_tournament(
    selected: pd.DataFrame,
    minimum_prior_errors: int = 24,
    rolling_window: int = 48,
    half_life: float = 18.0,
    coverage: float = 0.80,
) -> pd.DataFrame:
    """Evaluate predeclared prior-only interval methods on the fixed policy rows."""
    methods = ["rolling_q80", "exp_weighted_q80", "target_shrunk_q80", "ewma_gaussian"]
    rows: list[dict] = []
    work = selected.copy()
    work["_period"] = pd.PeriodIndex(work["target_period"], freq="M")
    work = work.sort_values(["target_series", "forecast_stage", "_period"])
    z = NormalDist().inv_cdf((1.0 + coverage) / 2.0)

    for (target, stage), group in work.groupby(["target_series", "forecast_stage"]):
        for _, row in group.iterrows():
            period = row["_period"]
            prior_group = group.loc[group["_period"] < period].tail(rolling_window)
            if len(prior_group) < minimum_prior_errors:
                continue
            group_errors = pd.to_numeric(prior_group["abs_error"], errors="coerce").dropna().to_numpy(float)

            target_prior = work.loc[
                (work["target_series"] == target) & (work["_period"] < period)
            ].copy()
            target_prior = (
                target_prior.groupby("_period", as_index=False)["abs_error"].median().tail(rolling_window)
            )
            target_errors = pd.to_numeric(target_prior["abs_error"], errors="coerce").dropna().to_numpy(float)
            if len(target_errors) < minimum_prior_errors:
                target_errors = group_errors

            ages = np.arange(len(group_errors) - 1, -1, -1, dtype=float)
            weights = np.power(0.5, ages / half_life)
            widths = {
                "rolling_q80": _quantile(group_errors, coverage),
                "exp_weighted_q80": _weighted_quantile(group_errors, weights, coverage),
                "target_shrunk_q80": (
                    0.70 * _quantile(group_errors, coverage)
                    + 0.30 * _quantile(target_errors, coverage)
                ),
                "ewma_gaussian": z * float(np.sqrt(np.average(np.square(group_errors), weights=weights))),
            }
            for method in methods:
                width = max(0.0, float(widths[method]))
                point = float(row["point_forecast"])
                actual = float(row["actual"])
                lower = point - width
                upper = point + width
                rows.append(
                    {
                        "target_series": target,
                        "forecast_stage": stage,
                        "target_period": str(period),
                        "model_name": row["model_name"],
                        "interval_method": method,
                        "point_forecast": point,
                        "actual": actual,
                        "lower_80": lower,
                        "upper_80": upper,
                        "interval_half_width": width,
                        "interval_covered": bool(lower <= actual <= upper),
                        "interval_score": _interval_score(actual, lower, upper),
                        "prior_error_count": int(len(prior_group)),
                        "calibration_cutoff_period": str(prior_group["_period"].iloc[-1]),
                    }
                )
    return pd.DataFrame(rows)


def summarise_interval_tournament(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    return (
        frame.groupby("interval_method")
        .agg(
            observations=("interval_covered", "count"),
            coverage=("interval_covered", "mean"),
            average_half_width=("interval_half_width", "mean"),
            mean_interval_score=("interval_score", "mean"),
            median_interval_score=("interval_score", "median"),
        )
        .reset_index()
        .sort_values(["mean_interval_score", "interval_method"])
    )





def compare_policies_on_common_sample(
    fixed: pd.DataFrame,
    shadow: pd.DataFrame,
    minimum_prior_errors: int = 24,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare the fixed and shadow policies on exactly the same eligible months.

    Raw fixed-policy summaries use all available months, while the prior-only shadow
    can only operate after its warm-up. This helper restricts both policies to the
    same target/stage/month keys so ratios are economically meaningful.
    """
    if fixed.empty or shadow.empty:
        return pd.DataFrame(), pd.DataFrame()

    keys = ["target_series", "forecast_stage", "target_period"]
    shadow_usable = shadow.loc[
        pd.to_numeric(shadow["prior_period_count"], errors="coerce") >= minimum_prior_errors
    ].copy()
    if shadow_usable.empty:
        return pd.DataFrame(), pd.DataFrame()

    eligible_keys = shadow_usable[keys].drop_duplicates()
    fixed_common = fixed.merge(eligible_keys, on=keys, how="inner")
    shadow_common = shadow_usable.merge(eligible_keys, on=keys, how="inner")

    fixed_summary = summarise_forecasts(fixed_common).rename(
        columns={column: f"fixed_{column}" for column in [
            "observations", "rmse", "mae", "bias", "median_ae",
            "p90_abs_error", "max_abs_error", "model_name"
        ]}
    )
    shadow_summary = summarise_forecasts(shadow_common).rename(
        columns={column: f"shadow_{column}" for column in [
            "observations", "rmse", "mae", "bias", "median_ae",
            "p90_abs_error", "max_abs_error", "model_name"
        ]}
    )
    comparison = fixed_summary.merge(
        shadow_summary, on=["target_series", "forecast_stage"], how="inner"
    )
    for metric in ["rmse", "mae", "p90_abs_error", "max_abs_error"]:
        comparison[f"shadow_to_fixed_{metric}_ratio"] = (
            comparison[f"shadow_{metric}"] / comparison[f"fixed_{metric}"]
        )
    comparison["absolute_bias_improved"] = (
        comparison["shadow_bias"].abs() < comparison["fixed_bias"].abs()
    )
    comparison["shadow_rmse_improved"] = comparison["shadow_to_fixed_rmse_ratio"] < 1.0
    comparison["shadow_mae_improved"] = comparison["shadow_to_fixed_mae_ratio"] < 1.0
    comparison["shadow_tail_improved"] = comparison["shadow_to_fixed_p90_abs_error_ratio"] < 1.0

    long_rows: list[dict] = []
    for policy_name, frame in [("stable_candidate", fixed_common), ("adaptive_shadow", shadow_common)]:
        for (target, stage), group in frame.groupby(["target_series", "forecast_stage"]):
            long_rows.append({
                "target_series": target,
                "forecast_stage": stage,
                "policy": policy_name,
                **_metrics(group),
            })
    common_summary = pd.DataFrame(long_rows).sort_values(
        ["target_series", "forecast_stage", "policy"]
    )
    return comparison.sort_values(["target_series", "forecast_stage"]), common_summary


def summarise_shadow_switching(
    shadow: pd.DataFrame, minimum_prior_errors: int = 24
) -> pd.DataFrame:
    if shadow.empty:
        return pd.DataFrame()
    usable = shadow.loc[
        pd.to_numeric(shadow["prior_period_count"], errors="coerce") >= minimum_prior_errors
    ].copy()
    if usable.empty:
        return pd.DataFrame()
    rows: list[dict] = []
    for (target, stage), group in usable.groupby(["target_series", "forecast_stage"]):
        stable_name = policy_model(str(target), str(stage))
        selected = group.get("selected_model", group["model_name"]).astype(str)
        rows.append({
            "target_series": target,
            "forecast_stage": stage,
            "eligible_months": int(len(group)),
            "switches": int(group["selection_changed"].fillna(False).astype(bool).sum()),
            "distinct_selected_models": int(selected.nunique()),
            "stable_policy_share": float((selected == stable_name).mean()),
            "most_selected_model": str(selected.value_counts().index[0]),
        })
    return pd.DataFrame(rows).sort_values(["target_series", "forecast_stage"])


def selected_interval_diagnostics(
    intervals: pd.DataFrame, method: str = SELECTED_INTERVAL_METHOD
) -> pd.DataFrame:
    if intervals.empty:
        return pd.DataFrame()
    selected = intervals.loc[intervals["interval_method"] == method].copy()
    if selected.empty:
        raise RuntimeError(f"Selected interval method {method} is absent from the tournament.")
    grouped = (
        selected.groupby(["target_series", "forecast_stage"])
        .agg(
            observations=("interval_covered", "count"),
            coverage=("interval_covered", "mean"),
            average_half_width=("interval_half_width", "mean"),
            mean_interval_score=("interval_score", "mean"),
            median_interval_score=("interval_score", "median"),
        )
        .reset_index()
        .sort_values(["target_series", "forecast_stage"])
    )
    return grouped

def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No rows."
    display = frame.copy()
    for column in display.select_dtypes(include=["float"]).columns:
        display[column] = display[column].map(lambda value: f"{value:.4f}")
    columns = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join(["---"] * len(columns)) + "|",
    ]
    for row in display.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def run_policy_evaluation(
    repository: MacroRepository | None = None,
    backtest_id: str | None = None,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    if backtest_id is None:
        latest = repository.query_df(
            """
            SELECT backtest_id
            FROM inflation_vintage_backtest_runs
            WHERE status IN ('success', 'partial')
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        if latest.empty:
            raise RuntimeError("No Model 1B vintage backtest is available.")
        backtest_id = str(latest.iloc[0]["backtest_id"])

    results = repository.query_df(
        """
        SELECT *
        FROM inflation_vintage_backtest_results
        WHERE backtest_id = ?
        ORDER BY target_series, forecast_stage, target_period, model_name
        """,
        [backtest_id],
    )
    if results.empty:
        raise RuntimeError(f"Vintage backtest {backtest_id} contains no forecasts.")

    fixed = select_fixed_policy(results)
    shadow = select_prior_only_shadow(results)
    fixed_summary = summarise_forecasts(fixed)
    shadow_usable = shadow.loc[shadow["prior_period_count"] >= ShadowSelectorConfig().minimum_prior_errors]
    shadow_summary = summarise_forecasts(shadow_usable) if not shadow_usable.empty else pd.DataFrame()
    common_comparison, common_summary = compare_policies_on_common_sample(
        fixed, shadow, ShadowSelectorConfig().minimum_prior_errors
    )
    switching_summary = summarise_shadow_switching(
        shadow, ShadowSelectorConfig().minimum_prior_errors
    )
    intervals = interval_tournament(fixed)
    interval_summary = summarise_interval_tournament(intervals)
    selected_interval_summary = selected_interval_diagnostics(intervals)

    report_dir = settings.project_root / "reports" / "inflation_policy"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"model1b_policy_evaluation_{timestamp}.md"
    fixed_csv = report_dir / f"model1b_fixed_policy_metrics_{timestamp}.csv"
    shadow_csv = report_dir / f"model1b_shadow_policy_metrics_{timestamp}.csv"
    interval_csv = report_dir / f"model1b_interval_tournament_{timestamp}.csv"
    common_csv = report_dir / f"model1b_common_sample_policy_comparison_{timestamp}.csv"
    switching_csv = report_dir / f"model1b_shadow_switching_{timestamp}.csv"
    selected_interval_csv = report_dir / f"model1b_selected_interval_diagnostics_{timestamp}.csv"
    fixed_summary.to_csv(fixed_csv, index=False)
    shadow_summary.to_csv(shadow_csv, index=False)
    interval_summary.to_csv(interval_csv, index=False)
    common_comparison.to_csv(common_csv, index=False)
    switching_summary.to_csv(switching_csv, index=False)
    selected_interval_summary.to_csv(selected_interval_csv, index=False)

    policy_rows = []
    for target, stage_map in STABLE_POLICY.items():
        for stage, model in stage_map.items():
            policy_rows.append((target, stage, model))
    lines = [
        "# MacroPulse Model 1B v0.4.1 Common-Sample Policy Verification",
        "",
        f"- Backtest ID: `{backtest_id}`",
        "- Status: **development research**",
        "- Fixed policy is a production candidate, not an approved production policy.",
        "",
        "## Stable candidate policy",
        "",
        "| Target | Stage | Component |",
        "|---|---|---|",
    ]
    lines.extend(f"| {target} | {stage} | {model} |" for target, stage, model in policy_rows)
    lines.extend(["", "## Fixed-policy performance", "", _markdown_table(fixed_summary)])
    if not shadow_summary.empty:
        lines.extend(["", "## Prior-only shadow performance (raw eligible sample)", "", _markdown_table(shadow_summary)])
    lines.extend(["", "## Fixed versus shadow on identical eligible months", ""])
    lines.append(_markdown_table(common_comparison) if not common_comparison.empty else "No common eligible sample.")
    lines.extend(["", "## Shadow switching stability", ""])
    lines.append(_markdown_table(switching_summary) if not switching_summary.empty else "No eligible shadow periods.")
    lines.extend(["", "## Interval-method tournament", ""])
    lines.append(_markdown_table(interval_summary) if not interval_summary.empty else "No calibrated tournament rows.")
    lines.extend(["", f"## Selected interval candidate: {SELECTED_INTERVAL_METHOD}", ""])
    lines.append(_markdown_table(selected_interval_summary) if not selected_interval_summary.empty else "No selected interval rows.")
    lines.extend(
        [
            "",
            "## Governance interpretation",
            "",
            "The fixed map was chosen for stability using the completed vintage evidence. "
            "The shadow selector uses only earlier forecast errors and remains non-production. "
            "The interval tournament is diagnostic; a method must not be promoted solely because "
            "it wins on the same evaluation sample.",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "backtest_id": backtest_id,
        "fixed": fixed,
        "shadow": shadow,
        "fixed_summary": fixed_summary,
        "shadow_summary": shadow_summary,
        "intervals": intervals,
        "interval_summary": interval_summary,
        "selected_interval_summary": selected_interval_summary,
        "common_comparison": common_comparison,
        "common_summary": common_summary,
        "switching_summary": switching_summary,
        "selected_interval_method": SELECTED_INTERVAL_METHOD,
        "report_path": str(report_path),
        "fixed_csv": str(fixed_csv),
        "shadow_csv": str(shadow_csv),
        "interval_csv": str(interval_csv),
        "common_csv": str(common_csv),
        "switching_csv": str(switching_csv),
        "selected_interval_csv": str(selected_interval_csv),
    }
