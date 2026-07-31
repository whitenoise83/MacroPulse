from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.labour.stages import LABOUR_FORECAST_STAGES
from macropulse.labour.versioning import current_labour_model_identity
from macropulse.settings import settings

EXPECTED_MODELS = {
    "Labour AR(1)",
    "Labour 12-Month Mean",
    "Labour Bridge Ridge",
    "Labour Factor Ridge",
    "Labour Equal-Weight Ensemble",
}


def _json_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {" | ".join(map(str, key)) if isinstance(key, tuple) else str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted((_json_safe(item) for item in value), key=str)
    return value


def _check(
    gate_name: str,
    check_name: str,
    status: str,
    observed_value: object,
    threshold: str,
    details: object | None = None,
) -> dict:
    return {
        "gate_name": gate_name,
        "check_name": check_name,
        "status": status,
        "observed_value": str(observed_value),
        "threshold": threshold,
        "details_json": json.dumps(_json_safe(details or {}), default=str, sort_keys=True),
    }


def _write_report(
    validation_id: str,
    status: str,
    backtest_id: str,
    checks: pd.DataFrame,
) -> Path:
    report_dir = settings.project_root / "reports" / "labour_validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"model1c_vintage_validation_{timestamp}.md"
    lines = [
        "# MacroPulse Model 1C Vintage Validation",
        "",
        f"- Validation ID: `{validation_id}`",
        f"- Backtest ID: `{backtest_id}`",
        f"- Status: **{status.upper()}**",
        "",
        "## Checks",
        "",
        "| Gate | Check | Status | Observed | Threshold |",
        "|---|---|---:|---:|---:|",
    ]
    for row in checks.itertuples(index=False):
        lines.append(
            f"| {row.gate_name} | {row.check_name} | {row.status} | "
            f"{row.observed_value} | {row.threshold} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This development-stage validation confirms the release timing, vintage information "
        "sets, model completeness, and robust reporting architecture. It does not select a "
        "production champion or approve the raw residual-based intervals.",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_labour_vintage_validation(
    repository: MacroRepository | None = None,
    backtest_id: str | None = None,
    minimum_months_per_stage: int = 36,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    identity = current_labour_model_identity()
    if backtest_id is None:
        latest = repository.query_df(
            """
            SELECT backtest_id
            FROM labour_vintage_backtest_runs
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        if latest.empty:
            raise RuntimeError("No labour vintage backtest exists. Run run_labour_vintage_backtest.py first.")
        backtest_id = str(latest.iloc[0]["backtest_id"])

    results = repository.query_df(
        "SELECT * FROM labour_vintage_backtest_results WHERE backtest_id = ?",
        [backtest_id],
    )
    if results.empty:
        raise RuntimeError(f"Labour vintage backtest {backtest_id} contains no results.")

    checks: list[dict] = []
    duplicate_count = int(results.duplicated([
        "target_series", "forecast_stage", "target_period", "model_name"
    ]).sum())
    checks.append(_check(
        "Data integrity", "One forecast per target, stage, month, and model",
        "pass" if duplicate_count == 0 else "fail", duplicate_count, "0 duplicates"
    ))

    release_violations = int((
        pd.to_datetime(results["forecast_date"]) >= pd.to_datetime(results["actual_release_date"])
    ).sum())
    checks.append(_check(
        "Econometric validity", "Forecast cutoff occurs before the initial target release",
        "pass" if release_violations == 0 else "fail", release_violations, "0 violations"
    ))

    future_rows = int((
        pd.to_datetime(results["max_observation_date"]) > pd.to_datetime(results["forecast_date"])
    ).sum())
    checks.append(_check(
        "Econometric validity", "No observation is dated after the information cutoff",
        "pass" if future_rows == 0 else "fail", future_rows, "0 future-dated information sets"
    ))

    leaked = int(results["target_leakage"].fillna(False).astype(bool).sum())
    checks.append(_check(
        "Econometric validity", "Target-month outcome is absent before its initial release",
        "pass" if leaked == 0 else "fail", leaked, "0 leaked forecasts"
    ))

    invalid_hashes = int((~results["information_set_hash"].astype(str).str.match(r"^[0-9a-f]{64}$")).sum())
    checks.append(_check(
        "Reproducibility", "Every forecast has a valid information-set hash",
        "pass" if invalid_hashes == 0 else "fail", invalid_hashes, "0 invalid hashes"
    ))

    model_sets = results.groupby([
        "target_series", "forecast_stage", "target_period"
    ])["model_name"].agg(set)
    incomplete_model_groups = int(sum(models != EXPECTED_MODELS for models in model_sets))
    checks.append(_check(
        "Data integrity", "Every evaluated information set contains all declared models",
        "pass" if incomplete_model_groups == 0 else "fail",
        incomplete_model_groups, "0 incomplete groups"
    ))

    expected_stages = {stage.code for stage in LABOUR_FORECAST_STAGES}
    stage_sets = results.groupby("target_series")["forecast_stage"].agg(set)
    incomplete_targets = int(sum(stages != expected_stages for stages in stage_sets))
    checks.append(_check(
        "Data integrity", "All declared release stages are represented for every target",
        "pass" if incomplete_targets == 0 else "fail",
        incomplete_targets, "0 incomplete targets", stage_sets.to_dict()
    ))

    evaluated = results.groupby([
        "target_series", "forecast_stage"
    ])["target_period"].nunique().sort_values()
    minimum_evaluated = int(evaluated.min())
    checks.append(_check(
        "Econometric validity", "Minimum evaluated months for every target and stage",
        "pass" if minimum_evaluated >= minimum_months_per_stage else "fail",
        minimum_evaluated, f">= {minimum_months_per_stage}", evaluated.to_dict()
    ))

    training_min = int(pd.to_numeric(results["training_observations"], errors="coerce").min())
    checks.append(_check(
        "Econometric validity", "Every forecast satisfies the configured training minimum",
        "pass" if training_min >= 120 else "fail", training_min, ">= 120 months"
    ))

    nonpositive_days = int((pd.to_numeric(results["days_to_release"]) <= 0).sum())
    checks.append(_check(
        "Econometric validity", "Every forecast has positive lead time to release",
        "pass" if nonpositive_days == 0 else "fail", nonpositive_days, "0 non-positive lead times"
    ))

    missing_robust = int(results[["abs_error", "squared_error", "direction_correct", "regime"]].isna().any(axis=1).sum())
    checks.append(_check(
        "Performance reporting", "Robust error and regime fields are complete",
        "pass" if missing_robust == 0 else "fail", missing_robust, "0 incomplete rows"
    ))

    regime_sets = results.groupby("target_series")["regime"].agg(set)
    required_regimes = {"pre_pandemic", "pandemic_dislocation", "post_2021"}
    incomplete_regimes = int(sum(not required_regimes.issubset(regimes) for regimes in regime_sets))
    checks.append(_check(
        "Performance reporting", "All declared economic regimes are represented for every target",
        "pass" if incomplete_regimes == 0 else "warning",
        incomplete_regimes, "0 incomplete targets", regime_sets.to_dict()
    ))

    coverage = results.groupby([
        "target_series", "forecast_stage", "model_name"
    ])["interval_covered"].mean()
    outside = coverage[(coverage < 0.50) | (coverage > 0.95)]
    checks.append(_check(
        "Uncertainty calibration", "Development 80% intervals are not grossly miscalibrated",
        "pass" if outside.empty else "warning",
        f"{len(outside)} groups outside range",
        "each group between 50% and 95%",
        outside.to_dict(),
    ))

    checks_frame = pd.DataFrame(checks)
    failures = int((checks_frame["status"] == "fail").sum())
    warnings = int((checks_frame["status"] == "warning").sum())
    passed = int((checks_frame["status"] == "pass").sum())
    status = "fail" if failures else ("conditional" if warnings else "pass")
    validation_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    report_path = _write_report(validation_id, status, backtest_id, checks_frame)
    checks_frame["validation_id"] = validation_id
    checks_frame["created_at"] = created_at
    checks_frame = checks_frame[[
        "validation_id", "gate_name", "check_name", "status", "observed_value",
        "threshold", "details_json", "created_at"
    ]]
    run_record = pd.DataFrame([{
        "validation_id": validation_id,
        "backtest_id": backtest_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "created_at": created_at,
        "status": status,
        "passed_gates": passed,
        "failed_gates": failures,
        "warning_gates": warnings,
        "report_path": str(report_path),
        "summary_json": json.dumps({
            "passed": passed, "failed": failures, "warnings": warnings,
        }),
        "notes": "Model 1C development vintage validation; no production approval implied.",
    }])
    repository.save_labour_validation_outputs(run_record, checks_frame)
    return {
        "validation_id": validation_id,
        "backtest_id": backtest_id,
        "status": status,
        "passed": passed,
        "failed": failures,
        "warnings": warnings,
        "checks": checks_frame,
        "report_path": report_path,
    }
