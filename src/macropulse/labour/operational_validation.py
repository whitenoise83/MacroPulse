from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.governance.versioning import information_set_hash
from macropulse.labour.live import governance_signature, model_state_hash
from macropulse.labour.policy import SELECTED_INTERVAL_METHOD, STABLE_POLICY, policy_model
from macropulse.labour.stages import LABOUR_STAGE_MAP
from macropulse.labour.versioning import current_labour_model_identity
from macropulse.settings import settings


@dataclass(frozen=True)
class OperationalThresholds:
    minimum_targets: int = 3
    minimum_prior_errors: int = 24
    maximum_news_residual: float = 1e-8


def _check(
    gate_name: str,
    check_name: str,
    status: str,
    observed_value: Any,
    threshold: str,
    details: Any | None = None,
) -> dict[str, Any]:
    return {
        "gate_name": gate_name,
        "check_name": check_name,
        "status": status,
        "observed_value": str(observed_value),
        "threshold": threshold,
        "details_json": json.dumps(details or {}, sort_keys=True, default=str),
    }


def evaluate_live_run_frames(
    run: pd.Series,
    forecasts: pd.DataFrame,
    components: pd.DataFrame,
    coefficients: pd.DataFrame,
    information_set: pd.DataFrame,
    news: pd.DataFrame,
    thresholds: OperationalThresholds | None = None,
) -> pd.DataFrame:
    thresholds = thresholds or OperationalThresholds()
    checks: list[dict[str, Any]] = []

    checks.append(
        _check(
            "Operational reliability",
            "Governed live run completed successfully",
            "pass" if str(run["status"]) == "success" else "fail",
            run["status"],
            "success",
        )
    )
    unique_targets = int(forecasts["target_series"].nunique()) if not forecasts.empty else 0
    duplicate_targets = int(forecasts.duplicated(["target_series"]).sum()) if not forecasts.empty else 0
    checks.append(
        _check(
            "Data integrity",
            "Exactly one governed headline exists for each labour target",
            "pass" if unique_targets == thresholds.minimum_targets and duplicate_targets == 0 else "fail",
            f"{unique_targets} targets; {duplicate_targets} duplicates",
            f"{thresholds.minimum_targets} targets and 0 duplicates",
        )
    )

    invalid_stages = sorted(
        set(forecasts.get("forecast_stage", pd.Series(dtype=str)).astype(str))
        .difference(LABOUR_STAGE_MAP)
    )
    checks.append(
        _check(
            "Policy governance",
            "Every live forecast uses a declared release stage",
            "pass" if not invalid_stages else "fail",
            len(invalid_stages),
            "0 invalid stages",
            invalid_stages,
        )
    )

    policy_violations: list[dict[str, str]] = []
    for row in forecasts.itertuples(index=False):
        expected = policy_model(str(row.target_series), str(row.forecast_stage))
        if str(row.stable_model_name) != expected:
            policy_violations.append(
                {
                    "target_series": str(row.target_series),
                    "forecast_stage": str(row.forecast_stage),
                    "observed": str(row.stable_model_name),
                    "expected": expected,
                }
            )
    checks.append(
        _check(
            "Policy governance",
            "Stable live policy follows the validated target-stage map",
            "pass" if not policy_violations else "fail",
            len(policy_violations),
            "0 violations",
            policy_violations,
        )
    )

    component_violations: list[dict[str, str]] = []
    for row in forecasts.itertuples(index=False):
        match = components.loc[
            (components["target_series"] == row.target_series)
            & (components["model_name"] == row.stable_model_name)
        ]
        if match.empty or not np.isclose(
            float(match.iloc[0]["point_forecast"]),
            float(row.stable_point_forecast),
            atol=1e-10,
            rtol=0.0,
        ):
            component_violations.append(
                {
                    "target_series": str(row.target_series),
                    "stable_model": str(row.stable_model_name),
                }
            )
    checks.append(
        _check(
            "Reproducibility",
            "Every headline matches its stored model component",
            "pass" if not component_violations else "fail",
            len(component_violations),
            "0 mismatches",
            component_violations,
        )
    )

    shadow_violations = int(
        (
            forecasts["shadow_model_name"].isna()
            | forecasts["shadow_point_forecast"].isna()
        ).sum()
    ) if not forecasts.empty else thresholds.minimum_targets
    checks.append(
        _check(
            "Challenger governance",
            "Adaptive forecasts are stored separately as shadow outputs",
            "pass" if shadow_violations == 0 else "fail",
            shadow_violations,
            "0 missing shadow outputs",
        )
    )

    interval_method_violations = int(
        (forecasts["interval_method"].astype(str) != SELECTED_INTERVAL_METHOD).sum()
    ) if not forecasts.empty else thresholds.minimum_targets
    checks.append(
        _check(
            "Uncertainty calibration",
            "Every live interval uses the validated candidate method",
            "pass" if interval_method_violations == 0 else "fail",
            interval_method_violations,
            f"0 methods other than {SELECTED_INTERVAL_METHOD}",
        )
    )
    finite_widths = pd.to_numeric(forecasts.get("interval_half_width"), errors="coerce")
    invalid_widths = int((~np.isfinite(finite_widths) | (finite_widths <= 0)).sum())
    checks.append(
        _check(
            "Uncertainty calibration",
            "Every live interval has a finite positive half-width",
            "pass" if invalid_widths == 0 else "fail",
            invalid_widths,
            "0 invalid widths",
        )
    )
    minimum_prior = int(
        pd.to_numeric(forecasts.get("interval_prior_errors"), errors="coerce").min()
    ) if not forecasts.empty else 0
    checks.append(
        _check(
            "Uncertainty calibration",
            "Every live interval has sufficient strictly prior error history",
            "pass" if minimum_prior >= thresholds.minimum_prior_errors else "fail",
            minimum_prior,
            f">= {thresholds.minimum_prior_errors}",
        )
    )
    cutoff_violations: list[dict[str, str]] = []
    for row in forecasts.itertuples(index=False):
        if pd.Period(str(row.interval_cutoff_period), freq="M") >= pd.Period(str(row.target_period), freq="M"):
            cutoff_violations.append(
                {
                    "target_series": str(row.target_series),
                    "cutoff": str(row.interval_cutoff_period),
                    "target_period": str(row.target_period),
                }
            )
    checks.append(
        _check(
            "Econometric validity",
            "Live interval calibration uses only earlier target months",
            "pass" if not cutoff_violations else "fail",
            len(cutoff_violations),
            "0 violations",
            cutoff_violations,
        )
    )

    hash_fields = ["config_hash", "code_hash", "information_set_hash", "model_state_hash", "governance_signature"]
    invalid_hashes = [
        field for field in hash_fields
        if not isinstance(run.get(field), str) or len(str(run.get(field))) != 64
    ]
    checks.append(
        _check(
            "Reproducibility",
            "Governed run contains complete SHA-256 provenance hashes",
            "pass" if not invalid_hashes else "fail",
            len(invalid_hashes),
            "0 invalid hashes",
            invalid_hashes,
        )
    )

    computed_info_hash = information_set_hash(information_set)
    checks.append(
        _check(
            "Reproducibility",
            "Stored information-set hash reproduces from persisted observations",
            "pass" if computed_info_hash == str(run["information_set_hash"]) else "fail",
            computed_info_hash,
            str(run["information_set_hash"]),
        )
    )
    computed_state_hash = model_state_hash(components, coefficients)
    checks.append(
        _check(
            "Reproducibility",
            "Stored model-state hash reproduces from components and coefficients",
            "pass" if computed_state_hash == str(run["model_state_hash"]) else "fail",
            computed_state_hash,
            str(run["model_state_hash"]),
        )
    )
    computed_signature = governance_signature(run.to_dict(), forecasts)
    checks.append(
        _check(
            "Governance",
            "Governance signature reproduces from the persisted live payload",
            "pass" if computed_signature == str(run["governance_signature"]) else "fail",
            computed_signature,
            str(run["governance_signature"]),
        )
    )

    observation_dates = pd.to_datetime(information_set.get("observation_date"), errors="coerce")
    cutoff = pd.Timestamp(run["information_cutoff"])
    future_rows = int((observation_dates > cutoff).fillna(False).sum())
    checks.append(
        _check(
            "Econometric validity",
            "No persisted observation is dated after the live information cutoff",
            "pass" if future_rows == 0 else "fail",
            future_rows,
            "0 future-dated observations",
        )
    )

    leakage: list[dict[str, str]] = []
    for row in forecasts.itertuples(index=False):
        target_rows = information_set.loc[information_set["series_id"] == row.target_series]
        if not target_rows.empty:
            latest = pd.to_datetime(target_rows["observation_date"]).max().to_period("M")
            if latest >= pd.Period(str(row.target_period), freq="M"):
                leakage.append(
                    {
                        "target_series": str(row.target_series),
                        "latest_observed": str(latest),
                        "target_period": str(row.target_period),
                    }
                )
    checks.append(
        _check(
            "Econometric validity",
            "Unreleased target-month outcomes are absent from the live information set",
            "pass" if not leakage else "fail",
            len(leakage),
            "0 leaked targets",
            leakage,
        )
    )

    candidate_id = str(run.get("candidate_validation_id") or "")
    checks.append(
        _check(
            "Governance",
            "Live run stores a candidate-validation reference",
            "pass" if len(candidate_id) == 36 else "fail",
            candidate_id,
            "valid candidate validation ID",
        )
    )

    news_targets = int(news["target_series"].nunique()) if not news.empty else 0
    checks.append(
        _check(
            "Operational reliability",
            "Every governed headline has a news-decomposition status",
            "pass" if news_targets == unique_targets else "fail",
            news_targets,
            f"{unique_targets} targets",
        )
    )
    comparable = news.loc[news["status"] == "success"].copy() if not news.empty else pd.DataFrame()
    maximum_residual = float(
        pd.to_numeric(comparable.get("residual_interaction"), errors="coerce").abs().max()
    ) if not comparable.empty else 0.0
    checks.append(
        _check(
            "Operational reliability",
            "Comparable labour news decompositions reconcile arithmetically",
            "pass" if maximum_residual <= thresholds.maximum_news_residual else "fail",
            maximum_residual,
            f"<= {thresholds.maximum_news_residual:g}",
        )
    )
    return pd.DataFrame(checks)


def _write_report(
    validation_id: str,
    run_id: str,
    status: str,
    checks: pd.DataFrame,
) -> Path:
    report_dir = settings.project_root / "reports" / "labour_operational_validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"model1c_live_validation_{timestamp}.md"
    identity = current_labour_model_identity()
    lines = [
        f"# MacroPulse Model 1C v{identity.model_version} Governed Live Validation",
        "",
        f"- Validation ID: `{validation_id}`",
        f"- Live run ID: `{run_id}`",
        f"- Status: **{status.upper()}**",
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
            (
                "The run is a production-governed live forecast. A passing operational "
                "validation demonstrates reproducibility, stable-policy control, prior-only "
                "intervals, shadow separation, and news reconciliation."
                if identity.lifecycle_status == "production"
                else "The run is a governed live candidate, not a production approval. A "
                "passing operational validation demonstrates reproducibility, stable-policy "
                "control, prior-only intervals, shadow separation, and news reconciliation."
            ),
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_labour_operational_validation(
    repository: MacroRepository | None = None,
    run_id: str | None = None,
    thresholds: OperationalThresholds | None = None,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    if run_id is None:
        latest = repository.query_df(
            """
            SELECT run_id
            FROM labour_live_runs
            ORDER BY run_timestamp DESC
            LIMIT 1
            """
        )
        if latest.empty:
            raise RuntimeError("No governed Model 1C live run is available.")
        run_id = str(latest.iloc[0]["run_id"])

    run_frame = repository.query_df(
        "SELECT * FROM labour_live_runs WHERE run_id = ?", [run_id]
    )
    if run_frame.empty:
        raise RuntimeError(f"Governed Model 1C run {run_id} does not exist.")
    forecasts = repository.query_df(
        "SELECT * FROM labour_live_forecasts WHERE run_id = ? ORDER BY target_series",
        [run_id],
    )
    components = repository.query_df(
        "SELECT * FROM labour_live_components WHERE run_id = ? ORDER BY target_series, model_name",
        [run_id],
    )
    coefficients = repository.query_df(
        "SELECT * FROM labour_coefficients WHERE run_id = ? ORDER BY target_series, model_name, feature",
        [run_id],
    )
    information_set = repository.labour_live_information_set(run_id)
    news = repository.query_df(
        "SELECT * FROM labour_news_runs WHERE current_run_id = ? ORDER BY target_series",
        [run_id],
    )
    checks = evaluate_live_run_frames(
        run_frame.iloc[0], forecasts, components, coefficients, information_set, news,
        thresholds=thresholds,
    )
    candidate_id = str(run_frame.iloc[0]["candidate_validation_id"])
    candidate = repository.query_df(
        "SELECT status, passed_gates, failed_gates, warning_gates FROM labour_validation_runs WHERE validation_id = ?",
        [candidate_id],
    )
    candidate_passed = (
        not candidate.empty
        and str(candidate.iloc[0]["status"]) == "pass"
        and int(candidate.iloc[0]["failed_gates"]) == 0
        and int(candidate.iloc[0]["warning_gates"]) == 0
    )
    candidate_check = pd.DataFrame(
        [
            _check(
                "Governance",
                "Referenced candidate validation exists and passed without warnings",
                "pass" if candidate_passed else "fail",
                (
                    f"{candidate.iloc[0]['status']} / {int(candidate.iloc[0]['passed_gates'])} passed"
                    if not candidate.empty else "missing"
                ),
                "pass with 0 failures and 0 warnings",
            )
        ]
    )
    checks = pd.concat([checks, candidate_check], ignore_index=True)
    failed = int((checks["status"] == "fail").sum())
    warnings = int((checks["status"] == "warning").sum())
    passed = int((checks["status"] == "pass").sum())
    status = "fail" if failed else ("conditional" if warnings else "pass")
    validation_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    report = _write_report(validation_id, run_id, status, checks)
    identity = current_labour_model_identity()
    persisted = checks.copy()
    persisted.insert(0, "validation_id", validation_id)
    persisted["created_at"] = created_at
    run_record = pd.DataFrame(
        [
            {
                "validation_id": validation_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "backtest_id": str(run_frame.iloc[0]["backtest_id"]),
                "created_at": created_at,
                "status": status,
                "passed_gates": passed,
                "failed_gates": failed,
                "warning_gates": warnings,
                "report_path": str(report),
                "summary_json": json.dumps(
                    {
                        "validation_type": "governed_live_operational",
                        "live_run_id": run_id,
                        "passed": passed,
                        "failed": failed,
                        "warnings": warnings,
                    },
                    sort_keys=True,
                ),
                "notes": (
                    f"Model 1C v{identity.model_version} "
                    f"{identity.lifecycle_status} governed live operational validation."
                ),
            }
        ]
    )
    run_record = run_record[
        [
            "validation_id",
            "backtest_id",
            "model_id",
            "model_version",
            "created_at",
            "status",
            "passed_gates",
            "failed_gates",
            "warning_gates",
            "report_path",
            "summary_json",
            "notes",
        ]
    ]
    persisted = persisted[
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
    repository.save_labour_validation_outputs(run_record, persisted)
    return {
        "validation_id": validation_id,
        "run_id": run_id,
        "status": status,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "report_path": str(report),
        "checks": checks,
    }
