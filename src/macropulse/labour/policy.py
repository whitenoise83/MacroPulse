from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.settings import settings


SELECTED_INTERVAL_METHOD = "exp_weighted_q80"

# This map is a development candidate derived from the completed vintage stage
# metrics.  It is intentionally stable and must not be treated as production
# until common-sample shadow evidence and candidate validation are complete.
STABLE_POLICY: dict[str, dict[str, str]] = {
    "PAYEMS": {
        "month_open": "Labour 12-Month Mean",
        "after_week_1": "Labour Equal-Weight Ensemble",
        "after_week_2": "Labour Bridge Ridge",
        "month_end": "Labour Bridge Ridge",
        "pre_employment_report": "Labour Bridge Ridge",
    },
    "UNRATE": {
        "month_open": "Labour Equal-Weight Ensemble",
        "after_week_1": "Labour Equal-Weight Ensemble",
        "after_week_2": "Labour Equal-Weight Ensemble",
        "month_end": "Labour Equal-Weight Ensemble",
        "pre_employment_report": "Labour Equal-Weight Ensemble",
    },
    "CES0500000003": {
        "month_open": "Labour Bridge Ridge",
        "after_week_1": "Labour Bridge Ridge",
        "after_week_2": "Labour Equal-Weight Ensemble",
        "month_end": "Labour Equal-Weight Ensemble",
        "pre_employment_report": "Labour Equal-Weight Ensemble",
    },
}


@dataclass(frozen=True)
class ShadowSelectorConfig:
    minimum_prior_errors: int = 24
    rolling_window: int = 36
    switch_hurdle: float = 0.03
    mae_guard: float = 1.05
    median_guard: float = 1.10
    tail_guard: float = 1.10
    max_error_guard: float = 1.15
    directional_guard: float = 0.03


def policy_model(target_series: str, forecast_stage: str) -> str:
    try:
        return STABLE_POLICY[target_series][forecast_stage]
    except KeyError as exc:
        raise ValueError(
            "No Model 1C stable-policy component is declared for "
            f"{target_series} / {forecast_stage}."
        ) from exc


def _metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    errors = pd.to_numeric(frame["error"], errors="coerce")
    usable = frame.loc[errors.notna()].copy()
    errors = errors.dropna().astype(float)
    if errors.empty:
        return {}
    absolute = errors.abs()
    direction = pd.to_numeric(usable.get("direction_correct"), errors="coerce")
    return {
        "observations": int(len(errors)),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "mae": float(absolute.mean()),
        "bias": float(errors.mean()),
        "median_ae": float(absolute.median()),
        "p90_abs_error": float(absolute.quantile(0.90)),
        "max_abs_error": float(absolute.max()),
        "directional_accuracy": float(direction.mean()) if direction.notna().any() else np.nan,
    }


def robust_score(metrics: Mapping[str, float | int]) -> float:
    """Target-unit score used only by the prior-only shadow challenger.

    Models are compared within a target/stage group, so all error terms have the
    same units.  RMSE remains important but MAE, median error and upper-tail error
    prevent a tiny crisis-sensitive RMSE advantage from driving unstable switches.
    """
    return float(
        0.40 * float(metrics["rmse"])
        + 0.25 * float(metrics["mae"])
        + 0.15 * float(metrics["p90_abs_error"])
        + 0.10 * float(metrics["median_ae"])
        + 0.10 * abs(float(metrics["bias"]))
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
        switch_count = 0
        for period in periods:
            prior = group.loc[group["_period"] < period]
            common_prior_periods = int(prior["_period"].nunique())
            metrics_by_model: dict[str, dict[str, float | int]] = {}
            selected = incumbent
            reason = "insufficient prior forecast errors"
            cutoff = str(prior["_period"].max()) if not prior.empty else None

            if common_prior_periods >= config.minimum_prior_errors:
                metrics_by_model = _candidate_metrics(prior, config.rolling_window)
                incumbent_metrics = metrics_by_model.get(incumbent)
                if incumbent_metrics:
                    incumbent_score = robust_score(incumbent_metrics)
                    eligible: list[tuple[float, str]] = [(incumbent_score, incumbent)]
                    incumbent_direction = float(incumbent_metrics.get("directional_accuracy", np.nan))
                    for model, metrics in metrics_by_model.items():
                        if model == incumbent:
                            continue
                        if int(metrics.get("observations", 0)) < config.minimum_prior_errors:
                            continue
                        score = robust_score(metrics)
                        direction = float(metrics.get("directional_accuracy", np.nan))
                        direction_gate = (
                            not np.isfinite(incumbent_direction)
                            or not np.isfinite(direction)
                            or direction >= incumbent_direction - config.directional_guard
                        )
                        gates = [
                            score <= incumbent_score * (1.0 - config.switch_hurdle),
                            float(metrics["mae"]) <= float(incumbent_metrics["mae"]) * config.mae_guard,
                            float(metrics["median_ae"]) <= float(incumbent_metrics["median_ae"]) * config.median_guard,
                            float(metrics["p90_abs_error"]) <= float(incumbent_metrics["p90_abs_error"]) * config.tail_guard,
                            float(metrics["max_abs_error"]) <= float(incumbent_metrics["max_abs_error"]) * config.max_error_guard,
                            direction_gate,
                        ]
                        if all(gates):
                            eligible.append((score, model))
                    eligible.sort(key=lambda item: (item[0], item[1]))
                    selected = eligible[0][1]
                    reason = (
                        "prior-only robust score and risk guards"
                        if selected != incumbent
                        else "stable incumbent retained after prior-only risk guards"
                    )

            current = group.loc[(group["_period"] == period) & (group["model_name"] == selected)]
            if current.empty:
                raise RuntimeError(
                    f"Selected model {selected} is missing for {target} {stage} {period}."
                )
            changed = selected != incumbent
            if changed:
                switch_count += 1
            row = current.iloc[0].to_dict()
            row.update(
                {
                    "selection_policy": "prior_only_shadow",
                    "selected_model": selected,
                    "previous_model": incumbent,
                    "selection_changed": changed,
                    "selection_reason": reason,
                    "prior_period_count": common_prior_periods,
                    "selection_cutoff_period": cutoff,
                    "selection_metrics_json": json.dumps(
                        metrics_by_model, sort_keys=True, default=str
                    ),
                    "cumulative_switch_count": switch_count,
                }
            )
            rows.append(row)
            incumbent = selected

    output = pd.DataFrame(rows)
    if not output.empty and "_period" in output:
        output = output.drop(columns=["_period"])
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


def compare_policies_on_common_sample(
    fixed: pd.DataFrame,
    shadow: pd.DataFrame,
    minimum_prior_errors: int = 24,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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

    metrics_columns = [
        "observations", "rmse", "mae", "bias", "median_ae",
        "p90_abs_error", "max_abs_error", "directional_accuracy", "model_name",
    ]
    fixed_summary = summarise_forecasts(fixed_common).rename(
        columns={column: f"fixed_{column}" for column in metrics_columns}
    )
    shadow_summary = summarise_forecasts(shadow_common).rename(
        columns={column: f"shadow_{column}" for column in metrics_columns}
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
    comparison["directional_accuracy_improved"] = (
        comparison["shadow_directional_accuracy"] > comparison["fixed_directional_accuracy"]
    )
    comparison["shadow_rmse_improved"] = comparison["shadow_to_fixed_rmse_ratio"] < 1.0
    comparison["shadow_mae_improved"] = comparison["shadow_to_fixed_mae_ratio"] < 1.0
    comparison["shadow_tail_improved"] = (
        comparison["shadow_to_fixed_p90_abs_error_ratio"] < 1.0
    )

    long_rows: list[dict] = []
    for policy_name, frame in [
        ("stable_candidate", fixed_common),
        ("adaptive_shadow", shadow_common),
    ]:
        for (target, stage), group in frame.groupby(["target_series", "forecast_stage"]):
            long_rows.append(
                {
                    "target_series": target,
                    "forecast_stage": stage,
                    "policy": policy_name,
                    **_metrics(group),
                }
            )
    common_summary = pd.DataFrame(long_rows).sort_values(
        ["target_series", "forecast_stage", "policy"]
    )
    return comparison.sort_values(["target_series", "forecast_stage"]), common_summary


def summarise_shadow_switching(
    shadow: pd.DataFrame,
    minimum_prior_errors: int = 24,
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
        rows.append(
            {
                "target_series": target,
                "forecast_stage": stage,
                "eligible_months": int(len(group)),
                "switches": int(group["selection_changed"].fillna(False).astype(bool).sum()),
                "distinct_selected_models": int(selected.nunique()),
                "stable_policy_share": float((selected == stable_name).mean()),
                "most_selected_model": str(selected.value_counts().index[0]),
            }
        )
    return pd.DataFrame(rows).sort_values(["target_series", "forecast_stage"])


def summarise_regime_performance(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "regime" not in frame:
        return pd.DataFrame()
    rows: list[dict] = []
    for (target, stage, regime), group in frame.groupby(
        ["target_series", "forecast_stage", "regime"]
    ):
        rows.append(
            {
                "target_series": target,
                "forecast_stage": stage,
                "regime": regime,
                **_metrics(group),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["target_series", "forecast_stage", "regime"]
    )


def attach_calibrated_intervals(
    selected: pd.DataFrame,
    calibrated: pd.DataFrame,
) -> pd.DataFrame:
    """Attach the selected prior-only intervals to policy forecasts.

    Vintage backtest rows already contain development-time residual intervals with
    columns such as ``lower_80``, ``upper_80`` and ``interval_covered``.  Merging
    calibrated rows without removing those legacy columns makes pandas create
    ``*_x``/``*_y`` suffixes, leaving no canonical ``interval_covered`` column for
    the policy summary.  The policy tournament must use the validated prior-only
    calibration exclusively, so legacy interval columns are deliberately dropped
    before the one-to-one merge.
    """
    if selected.empty or calibrated.empty:
        return pd.DataFrame()

    keys = ["target_series", "forecast_stage", "target_period", "model_name"]
    calibration_columns = [
        "calibration_id",
        "interval_method",
        "lower_80",
        "upper_80",
        "interval_covered",
        "interval_half_width",
        "interval_score",
        "prior_error_count",
        "calibration_cutoff_period",
    ]
    required_calibrated = set(keys + calibration_columns + ["calibration_status"])
    missing = sorted(required_calibrated.difference(calibrated.columns))
    if missing:
        raise ValueError(
            "Calibrated labour intervals are missing required columns: "
            f"{missing}"
        )

    usable = calibrated.loc[
        (calibrated["calibration_status"] == "calibrated")
        & (calibrated["interval_method"] == SELECTED_INTERVAL_METHOD)
    ].copy()
    if usable.empty:
        return pd.DataFrame()

    # Remove raw/residual interval fields from vintage backtest policy rows.
    # The calibrated fields below are the sole source of interval diagnostics.
    selected_clean = selected.drop(
        columns=[column for column in calibration_columns if column in selected.columns],
        errors="ignore",
    ).copy()
    merged = selected_clean.merge(
        usable[keys + calibration_columns],
        on=keys,
        how="inner",
        validate="one_to_one",
    )
    return merged.sort_values(["target_series", "forecast_stage", "target_period"])


def summarise_intervals(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    return (
        frame.groupby(["target_series", "forecast_stage"])
        .agg(
            observations=("interval_covered", "count"),
            coverage=("interval_covered", "mean"),
            average_half_width=("interval_half_width", "mean"),
            mean_interval_score=("interval_score", "mean"),
            median_interval_score=("interval_score", "median"),
            minimum_prior_errors=("prior_error_count", "min"),
        )
        .reset_index()
        .sort_values(["target_series", "forecast_stage"])
    )


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


def run_labour_policy_evaluation(
    repository: MacroRepository | None = None,
    backtest_id: str | None = None,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    if backtest_id is None:
        latest = repository.query_df(
            """
            SELECT backtest_id
            FROM labour_vintage_backtest_runs
            WHERE status IN ('success', 'partial')
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        if latest.empty:
            raise RuntimeError("No Model 1C vintage backtest is available.")
        backtest_id = str(latest.iloc[0]["backtest_id"])

    results = repository.query_df(
        """
        SELECT *
        FROM labour_vintage_backtest_results
        WHERE backtest_id = ?
        ORDER BY target_series, forecast_stage, target_period, model_name
        """,
        [backtest_id],
    )
    if results.empty:
        raise RuntimeError(f"Vintage backtest {backtest_id} contains no forecasts.")

    fixed = select_fixed_policy(results)
    shadow = select_prior_only_shadow(results)
    config = ShadowSelectorConfig()
    shadow_usable = shadow.loc[
        pd.to_numeric(shadow["prior_period_count"], errors="coerce")
        >= config.minimum_prior_errors
    ].copy()
    fixed_summary = summarise_forecasts(fixed)
    shadow_summary = (
        summarise_forecasts(shadow_usable) if not shadow_usable.empty else pd.DataFrame()
    )
    common_comparison, common_summary = compare_policies_on_common_sample(
        fixed, shadow, config.minimum_prior_errors
    )
    switching_summary = summarise_shadow_switching(
        shadow, config.minimum_prior_errors
    )
    regime_summary = summarise_regime_performance(fixed)

    calibration_run = repository.query_df(
        """
        SELECT calibration_id
        FROM labour_interval_calibration_runs
        WHERE backtest_id = ? AND status = 'success'
          AND method = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [backtest_id, SELECTED_INTERVAL_METHOD],
    )
    calibration_id: str | None = None
    calibrated = pd.DataFrame()
    if not calibration_run.empty:
        calibration_id = str(calibration_run.iloc[0]["calibration_id"])
        calibrated = repository.query_df(
            """
            SELECT *
            FROM labour_interval_calibrated_results
            WHERE calibration_id = ?
            ORDER BY target_series, forecast_stage, target_period, model_name
            """,
            [calibration_id],
        )
    fixed_intervals = attach_calibrated_intervals(fixed, calibrated)
    shadow_intervals = attach_calibrated_intervals(shadow_usable, calibrated)
    fixed_interval_summary = summarise_intervals(fixed_intervals)
    shadow_interval_summary = summarise_intervals(shadow_intervals)

    report_dir = settings.project_root / "reports" / "labour_policy"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"model1c_policy_evaluation_{timestamp}.md"
    paths = {
        "fixed_csv": report_dir / f"model1c_fixed_policy_metrics_{timestamp}.csv",
        "shadow_csv": report_dir / f"model1c_shadow_policy_metrics_{timestamp}.csv",
        "common_csv": report_dir / f"model1c_common_sample_policy_comparison_{timestamp}.csv",
        "switching_csv": report_dir / f"model1c_shadow_switching_{timestamp}.csv",
        "regime_csv": report_dir / f"model1c_fixed_policy_regimes_{timestamp}.csv",
        "fixed_interval_csv": report_dir / f"model1c_fixed_policy_intervals_{timestamp}.csv",
        "shadow_interval_csv": report_dir / f"model1c_shadow_policy_intervals_{timestamp}.csv",
    }
    for frame, key in [
        (fixed_summary, "fixed_csv"),
        (shadow_summary, "shadow_csv"),
        (common_comparison, "common_csv"),
        (switching_summary, "switching_csv"),
        (regime_summary, "regime_csv"),
        (fixed_interval_summary, "fixed_interval_csv"),
        (shadow_interval_summary, "shadow_interval_csv"),
    ]:
        frame.to_csv(paths[key], index=False)

    policy_rows = [
        (target, stage, model)
        for target, stage_map in STABLE_POLICY.items()
        for stage, model in stage_map.items()
    ]
    lines = [
        "# MacroPulse Model 1C v0.4.0.post1 Stable Policy Tournament",
        "",
        f"- Backtest ID: `{backtest_id}`",
        f"- Calibration ID: `{calibration_id or 'not available'}`",
        "- Status: **development research**",
        "- Stable policy is a candidate, not an approved production policy.",
        "- Adaptive selection is a prior-only shadow challenger.",
        "",
        "## Stable candidate policy",
        "",
        "| Target | Stage | Component |",
        "|---|---|---|",
    ]
    lines.extend(f"| {target} | {stage} | {model} |" for target, stage, model in policy_rows)
    lines.extend(["", "## Fixed-policy performance", "", _markdown_table(fixed_summary)])
    lines.extend(["", "## Prior-only shadow performance", "", _markdown_table(shadow_summary)])
    lines.extend(["", "## Fixed versus shadow on identical eligible months", "", _markdown_table(common_comparison)])
    lines.extend(["", "## Shadow switching stability", "", _markdown_table(switching_summary)])
    lines.extend(["", "## Fixed-policy regime performance", "", _markdown_table(regime_summary)])
    lines.extend([
        "",
        f"## Stable-policy intervals: {SELECTED_INTERVAL_METHOD}",
        "",
        _markdown_table(fixed_interval_summary),
        "",
        "## Shadow-policy intervals",
        "",
        _markdown_table(shadow_interval_summary),
        "",
        "## Governance interpretation",
        "",
        "The fixed map was selected from completed vintage evidence with explicit emphasis "
        "on typical error, crisis tails, bias, and stage stability. The adaptive selector "
        "uses only earlier forecast errors and remains shadow-only. Common-sample evidence "
        "must be reviewed before candidate validation; raw full-sample and shadow summaries "
        "must not be compared directly because their evaluation windows differ.",
    ])
    report_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "backtest_id": backtest_id,
        "calibration_id": calibration_id,
        "fixed": fixed,
        "shadow": shadow,
        "fixed_summary": fixed_summary,
        "shadow_summary": shadow_summary,
        "common_comparison": common_comparison,
        "common_summary": common_summary,
        "switching_summary": switching_summary,
        "regime_summary": regime_summary,
        "fixed_interval_summary": fixed_interval_summary,
        "shadow_interval_summary": shadow_interval_summary,
        "selected_interval_method": SELECTED_INTERVAL_METHOD,
        "report_path": str(report_path),
        **{key: str(value) for key, value in paths.items()},
    }
