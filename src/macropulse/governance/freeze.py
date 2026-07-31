from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd

from macropulse.backtesting.metrics import calculate_stage_metrics, calculate_stage_regime_metrics
from macropulse.backtesting.production_selection import (
    ROBUST_STAGE_ADAPTIVE_MODEL_NAME,
    STABLE_STAGE_POLICY_NAME,
)
from macropulse.data.repository import MacroRepository
from macropulse.governance.versioning import current_model_identity, load_governance_config
from macropulse.settings import settings


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    if frame.empty:
        return ["No data available."]
    view = frame[columns].copy()
    for column in columns:
        if pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].round(4)
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return lines


def _selection_distribution(diagnostics: pd.DataFrame, model_name: str) -> pd.DataFrame:
    frame = diagnostics.loc[diagnostics["model_name"] == model_name].copy()
    if frame.empty:
        return pd.DataFrame(columns=["forecast_stage", "selected_component", "forecasts"])
    frame["selected_component"] = frame["details_json"].map(
        lambda value: json.loads(value or "{}").get("selected_component", "Unknown")
    )
    return (
        frame.groupby(["forecast_stage", "selected_component"])
        .size()
        .rename("forecasts")
        .reset_index()
    )


def _selection_stability(diagnostics: pd.DataFrame) -> pd.DataFrame:
    frame = diagnostics.loc[
        diagnostics["model_name"] == ROBUST_STAGE_ADAPTIVE_MODEL_NAME
    ].copy()
    if frame.empty:
        return pd.DataFrame(columns=["forecast_stage", "forecasts", "switches", "average_duration"])
    frame["selected_component"] = frame["details_json"].map(
        lambda value: json.loads(value or "{}").get("selected_component", "Unknown")
    )
    rows: list[dict] = []
    for stage, group in frame.groupby("forecast_stage", sort=False):
        selected = group.sort_values("forecast_date")["selected_component"].astype(str).tolist()
        switches = sum(left != right for left, right in zip(selected, selected[1:]))
        durations: list[int] = []
        if selected:
            length = 1
            for left, right in zip(selected, selected[1:]):
                if left == right:
                    length += 1
                else:
                    durations.append(length)
                    length = 1
            durations.append(length)
        rows.append(
            {
                "forecast_stage": stage,
                "forecasts": len(selected),
                "switches": switches,
                "average_duration": sum(durations) / len(durations) if durations else 0,
            }
        )
    return pd.DataFrame(rows)


def generate_freeze_assessment(repository: MacroRepository | None = None) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    identity = current_model_identity().as_dict()
    governance = load_governance_config()
    champion = str(governance["model"].get("champion_model", STABLE_STAGE_POLICY_NAME))

    validation = repository.query_df(
        """
        SELECT *
        FROM validation_runs
        WHERE model_id = ? AND model_version = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [identity["model_id"], identity["model_version"]],
    )
    if validation.empty:
        raise RuntimeError("No v0.6.1 validation run exists. Run scripts\\run_validation.py first.")
    validation_row = validation.iloc[0]
    validation_id = str(validation_row["validation_id"])
    checks = repository.query_df(
        """
        SELECT gate_name, check_name, status, observed_value, threshold
        FROM validation_checks
        WHERE validation_id = ?
        ORDER BY gate_name, check_name
        """,
        [validation_id],
    )
    stage_backtest_id = str(validation_row["stage_backtest_id"])
    results = repository.query_df(
        "SELECT * FROM stage_backtest_results WHERE stage_backtest_id = ?",
        [stage_backtest_id],
    )
    diagnostics = repository.query_df(
        "SELECT * FROM stage_backtest_diagnostics WHERE stage_backtest_id = ?",
        [stage_backtest_id],
    )
    stage_metrics = calculate_stage_metrics(results)
    regime_metrics = calculate_stage_regime_metrics(results)
    champion_metrics = stage_metrics.loc[stage_metrics["model_name"] == champion]
    robust_metrics = stage_metrics.loc[
        stage_metrics["model_name"] == ROBUST_STAGE_ADAPTIVE_MODEL_NAME
    ]
    champion_regimes = regime_metrics.loc[regime_metrics["model_name"] == champion]
    stable_distribution = _selection_distribution(diagnostics, STABLE_STAGE_POLICY_NAME)
    robust_distribution = _selection_distribution(diagnostics, ROBUST_STAGE_ADAPTIVE_MODEL_NAME)
    stability = _selection_stability(diagnostics)

    live = repository.query_df(
        """
        SELECT COUNT(*) AS records
        FROM forecast_registry
        WHERE model_id = ? AND model_version = ?
        """,
        [identity["model_id"], identity["model_version"]],
    )
    has_live = int(live.iloc[0]["records"]) > 0
    failures = int((checks["status"] == "fail").sum())
    warnings = int((checks["status"] == "warning").sum())
    validation_status = str(validation_row["status"])
    if failures:
        readiness = "not_ready"
    elif not has_live:
        readiness = "not_ready_live_forecast_required"
    elif warnings:
        readiness = "conditional_owner_review"
    elif validation_status == "pass":
        readiness = "ready_for_model_owner_signoff"
    else:
        readiness = "conditional_owner_review"

    created_at = datetime.now(UTC).replace(tzinfo=None)
    output_dir = settings.project_root / "reports" / "freeze"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"model1a_freeze_assessment_{created_at.strftime('%Y%m%d_%H%M%S')}.md"

    lines = [
        "# MacroPulse Model 1A - GDP Production Freeze Assessment",
        "",
        f"- Model: `{identity['model_id']}`",
        f"- Candidate version: `{identity['model_version']}`",
        f"- Lifecycle: `{identity['lifecycle_status']}`",
        f"- Production policy: `{champion}`",
        f"- Shadow challenger: `{ROBUST_STAGE_ADAPTIVE_MODEL_NAME}`",
        f"- Validation ID: `{validation_id}`",
        f"- Validation status: **{validation_status.upper()}**",
        f"- Freeze readiness: **{readiness.upper()}**",
        f"- Governed live forecast for this version: **{'YES' if has_live else 'NO'}**",
        f"- Configuration hash: `{identity['config_hash']}`",
        f"- Code hash: `{identity['code_hash']}`",
        "",
        "## Automated gates",
        "",
    ]
    lines.extend(_markdown_table(checks, ["gate_name", "check_name", "status", "observed_value", "threshold"]))
    lines.extend(["", "## Stable production policy metrics", ""])
    lines.extend(
        _markdown_table(
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
    lines.extend(["", "## Robust adaptive shadow metrics", ""])
    lines.extend(
        _markdown_table(
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
    lines.extend(_markdown_table(stable_distribution, ["forecast_stage", "selected_component", "forecasts"]))
    lines.extend(["", "## Robust adaptive selections", ""])
    lines.extend(_markdown_table(robust_distribution, ["forecast_stage", "selected_component", "forecasts"]))
    lines.extend(["", "## Robust selector stability", ""])
    lines.extend(_markdown_table(stability, ["forecast_stage", "forecasts", "switches", "average_duration"]))
    lines.extend(["", "## Regime robustness", ""])
    lines.extend(
        _markdown_table(
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
            "## Model-owner decision",
            "",
            "- [ ] Review every warning and record the decision.",
            "- [ ] Confirm the stable stage-specific component map.",
            "- [ ] Confirm that the robust adaptive policy remains shadow-only.",
            "- [ ] Confirm the 80% interval method and revalidation triggers.",
            "- [ ] Confirm that the live dashboard and news decomposition use the stable production forecast.",
            "- [ ] Approve promotion to `US_GDP_NOWCAST_1A v1.0.0`.",
            "",
            "Promotion is a manual governance action. This script never changes the model version automatically.",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "readiness": readiness,
        "validation_id": validation_id,
        "validation_status": validation_status,
        "warnings": warnings,
        "failures": failures,
        "has_live_forecast": has_live,
        "report_path": output_path,
    }
