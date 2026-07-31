from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.inflation.stages import INFLATION_FORECAST_STAGES
from macropulse.inflation.versioning import current_inflation_model_identity
from macropulse.settings import settings


EXPECTED_MODELS = {
    "Inflation AR(1)",
    "Inflation 12-Month Mean",
    "Inflation Bridge Ridge",
    "Inflation Ridge-AR Ensemble",
}


def _json_key(value: object) -> str:
    """Return a deterministic JSON-compatible representation of a mapping key."""
    if isinstance(value, tuple):
        return " | ".join(str(item) for item in value)
    return str(value)


def _json_safe(value: object) -> object:
    """Recursively normalise pandas/MultiIndex diagnostic objects for JSON storage.

    Pandas ``Series.to_dict()`` uses tuple keys when the Series has a MultiIndex.
    Python's JSON encoder rejects tuple mapping keys before ``default=str`` is
    consulted. This normaliser preserves the information while converting all
    mapping keys to deterministic strings.
    """
    if isinstance(value, Mapping):
        return {_json_key(key): _json_safe(item) for key, item in value.items()}
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
    report_dir = settings.project_root / "reports" / "inflation_validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"model1b_vintage_validation_{timestamp}.md"
    lines = [
        "# MacroPulse Model 1B Vintage Validation",
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
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a development-stage vintage validation. Passing these checks confirms "
            "the information-set and release-timing architecture, not final production approval.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_inflation_vintage_validation(
    repository: MacroRepository | None = None,
    backtest_id: str | None = None,
    minimum_months_per_stage: int = 36,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    identity = current_inflation_model_identity()
    if backtest_id is None:
        latest = repository.query_df(
            """
            SELECT backtest_id
            FROM inflation_vintage_backtest_runs
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        if latest.empty:
            raise RuntimeError(
                "No inflation vintage backtest exists. Run run_inflation_vintage_backtest.py first."
            )
        backtest_id = str(latest.iloc[0]["backtest_id"])

    results = repository.query_df(
        """
        SELECT *
        FROM inflation_vintage_backtest_results
        WHERE backtest_id = ?
        """,
        [backtest_id],
    )
    if results.empty:
        raise RuntimeError(f"Vintage backtest {backtest_id} contains no results.")

    checks: list[dict] = []
    duplicate_count = int(
        results.duplicated(
            ["target_series", "forecast_stage", "target_period", "model_name"]
        ).sum()
    )
    checks.append(
        _check(
            "Data integrity",
            "One forecast per target, stage, month, and model",
            "pass" if duplicate_count == 0 else "fail",
            duplicate_count,
            "0 duplicates",
        )
    )

    release_violations = int(
        (pd.to_datetime(results["forecast_date"]) >= pd.to_datetime(results["actual_release_date"])).sum()
    )
    checks.append(
        _check(
            "Econometric validity",
            "Forecast cutoff occurs before the initial target release",
            "pass" if release_violations == 0 else "fail",
            release_violations,
            "0 violations",
        )
    )

    future_rows = int(
        (
            pd.to_datetime(results["max_observation_date"])
            > pd.to_datetime(results["forecast_date"])
        ).sum()
    )
    checks.append(
        _check(
            "Econometric validity",
            "No observation is dated after the information cutoff",
            "pass" if future_rows == 0 else "fail",
            future_rows,
            "0 future-dated information sets",
        )
    )

    leaked = int(results["target_leakage"].fillna(False).astype(bool).sum())
    checks.append(
        _check(
            "Econometric validity",
            "Target-month index is absent before its initial release",
            "pass" if leaked == 0 else "fail",
            leaked,
            "0 leaked forecasts",
        )
    )

    hashes = results["information_set_hash"].astype(str)
    invalid_hashes = int((hashes.str.len() != 64).sum())
    checks.append(
        _check(
            "Reproducibility",
            "Every forecast has a valid information-set hash",
            "pass" if invalid_hashes == 0 else "fail",
            invalid_hashes,
            "0 invalid hashes",
        )
    )

    model_counts = (
        results.groupby(["target_series", "forecast_stage", "target_period"])["model_name"]
        .agg(lambda values: set(values))
    )
    missing_model_groups = int(sum(models != EXPECTED_MODELS for models in model_counts))
    checks.append(
        _check(
            "Data integrity",
            "Every evaluated information set contains all declared models",
            "pass" if missing_model_groups == 0 else "fail",
            missing_model_groups,
            "0 incomplete groups",
        )
    )

    evaluated = (
        results.groupby(["target_series", "forecast_stage"])["target_period"]
        .nunique()
        .sort_values()
    )
    minimum_evaluated = int(evaluated.min())
    checks.append(
        _check(
            "Econometric validity",
            "Minimum evaluated months for every target and stage",
            "pass" if minimum_evaluated >= minimum_months_per_stage else "fail",
            minimum_evaluated,
            f">= {minimum_months_per_stage}",
            evaluated.to_dict(),
        )
    )

    expected_stages = {stage.code for stage in INFLATION_FORECAST_STAGES}
    stage_map = results.groupby("target_series")["forecast_stage"].agg(set)
    incomplete_targets = int(sum(stages != expected_stages for stages in stage_map))
    checks.append(
        _check(
            "Data integrity",
            "All declared release stages are represented for every target",
            "pass" if incomplete_targets == 0 else "fail",
            incomplete_targets,
            "0 incomplete targets",
            stage_map.to_dict(),
        )
    )

    training_min = int(pd.to_numeric(results["training_observations"]).min())
    checks.append(
        _check(
            "Econometric validity",
            "Every forecast satisfies the configured training minimum",
            "pass" if training_min >= 120 else "fail",
            training_min,
            ">= 120 months",
        )
    )

    calibration_run = repository.query_df(
        """
        SELECT *
        FROM inflation_interval_calibration_runs
        WHERE backtest_id = ? AND status = 'success'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [backtest_id],
    )
    calibration_id: str | None = None
    if calibration_run.empty:
        checks.append(
            _check(
                "Uncertainty calibration",
                "Prior-only interval calibration is available",
                "warning",
                "not available",
                "successful calibration required",
            )
        )
    else:
        calibration = calibration_run.iloc[0]
        calibration_id = str(calibration["calibration_id"])
        calibrated = repository.query_df(
            """
            SELECT *
            FROM inflation_interval_calibrated_results
            WHERE calibration_id = ?
            ORDER BY target_series, forecast_stage, model_name, target_period
            """,
            [calibration_id],
        )
        usable = calibrated.loc[
            calibrated["calibration_status"] == "calibrated"
        ].copy()
        checks.append(
            _check(
                "Uncertainty calibration",
                "Prior-only interval calibration is available",
                "pass" if not usable.empty else "fail",
                f"{len(usable)} calibrated rows",
                "> 0 calibrated rows",
                {"calibration_id": calibration_id, "method": calibration["method"]},
            )
        )

        target_periods = pd.PeriodIndex(usable["target_period"], freq="M")
        cutoff_periods = pd.PeriodIndex(usable["calibration_cutoff_period"], freq="M")
        lookahead = int((cutoff_periods >= target_periods).sum())
        checks.append(
            _check(
                "Econometric validity",
                "Interval calibration uses strictly prior target-month errors",
                "pass" if lookahead == 0 else "fail",
                lookahead,
                "0 look-ahead violations",
            )
        )

        required_prior = int(calibration["minimum_prior_errors"])
        minimum_prior = int(usable["prior_error_count"].min()) if not usable.empty else 0
        checks.append(
            _check(
                "Uncertainty calibration",
                "Every calibrated interval satisfies the prior-error minimum",
                "pass" if minimum_prior >= required_prior else "fail",
                minimum_prior,
                f">= {required_prior} prior errors",
            )
        )

        calibrated_counts = (
            usable.groupby(["target_series", "forecast_stage", "model_name"])[
                "target_period"
            ]
            .nunique()
            .sort_values()
        )
        minimum_calibrated = int(calibrated_counts.min()) if not calibrated_counts.empty else 0
        checks.append(
            _check(
                "Uncertainty calibration",
                "Minimum evaluated calibrated intervals for every target, stage, and model",
                "pass" if minimum_calibrated >= minimum_months_per_stage else "fail",
                minimum_calibrated,
                f">= {minimum_months_per_stage}",
                calibrated_counts.to_dict(),
            )
        )

        coverage = usable.groupby(
            ["target_series", "forecast_stage", "model_name"]
        )["interval_covered"].mean()
        outside = coverage[(coverage < 0.60) | (coverage > 0.95)]
        checks.append(
            _check(
                "Uncertainty calibration",
                "Prior-only 80% interval coverage is not grossly miscalibrated",
                "pass" if outside.empty else "warning",
                f"{len(outside)} groups outside range",
                "each group between 60% and 95%",
                outside.to_dict(),
            )
        )

    check_frame = pd.DataFrame(checks)
    failed = int((check_frame["status"] == "fail").sum())
    warnings = int((check_frame["status"] == "warning").sum())
    passed = int((check_frame["status"] == "pass").sum())
    status = "fail" if failed else ("conditional" if warnings else "pass")
    validation_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    report_path = _write_report(validation_id, status, backtest_id, check_frame)

    persisted_checks = check_frame.copy()
    persisted_checks.insert(0, "validation_id", validation_id)
    persisted_checks["created_at"] = created_at
    run_record = pd.DataFrame(
        [
            {
                "validation_id": validation_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "backtest_id": backtest_id,
                "created_at": created_at,
                "status": status,
                "passed_checks": passed,
                "failed_checks": failed,
                "warnings": warnings,
                "report_path": str(report_path),
                "summary_json": json.dumps(
                    {
                        "passed": passed,
                        "failed": failed,
                        "warnings": warnings,
                    }
                ),
                "notes": "Model 1B v0.3 development-stage vintage validation with prior-only interval calibration.",
            }
        ]
    )
    repository.save_inflation_validation_outputs(run_record, persisted_checks)
    return {
        "validation_id": validation_id,
        "backtest_id": backtest_id,
        "status": status,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "report_path": str(report_path),
        "checks": check_frame,
        "calibration_id": calibration_id,
    }
