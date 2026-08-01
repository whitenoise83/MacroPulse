from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from macropulse.data.repository import MacroRepository
from macropulse.labour.policy import SELECTED_INTERVAL_METHOD
from macropulse.labour.versioning import current_labour_model_identity
from macropulse.labour.validation_repair import (
    repair_operational_validation_metadata,
)
from macropulse.settings import settings

EXPECTED_CANDIDATE_PASSES = 39
EXPECTED_OPERATIONAL_PASSES = 20
EXPECTED_FREEZE_PASSES = 14
EXPECTED_TARGETS = 3
MAXIMUM_NEWS_RESIDUAL = 1.0e-8


def _load_governance() -> dict[str, Any]:
    config = yaml.safe_load(
        settings.labour_governance_path.read_text(encoding="utf-8")
    )
    if not isinstance(config, dict) or not isinstance(config.get("model"), dict):
        raise RuntimeError(
            "config/labour_governance.yml is missing the model mapping."
        )
    return config


def _approval_config(
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    model = config["model"]
    approval = model.get("approval")
    if not isinstance(approval, dict) or approval.get("status") != "approved":
        raise RuntimeError(
            "Model-owner approval is not recorded in labour_governance.yml."
        )
    if approval.get("approval_phrase") != "APPROVE MODEL 1C FREEZE":
        raise RuntimeError("The recorded Model 1C approval phrase is invalid.")
    return model, approval


def _json_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _validation_row(
    repository: MacroRepository,
    validation_id: str,
    validation_type: str,
    expected_passes: int,
) -> tuple[pd.Series, dict[str, Any]]:
    frame = repository.query_df(
        """
        SELECT validation_id, model_id, model_version, backtest_id, status,
               passed_gates, failed_gates, warning_gates, report_path, summary_json
        FROM labour_validation_runs
        WHERE validation_id = ?
        """,
        [validation_id],
    )
    if frame.empty:
        raise RuntimeError(
            f"Required validation ID {validation_id} is not present in DuckDB."
        )
    row = frame.iloc[0]
    summary = _json_mapping(row["summary_json"])
    if str(row["model_id"]) != "US_LABOUR_NOWCAST_1C":
        raise RuntimeError(
            f"Validation {validation_id} belongs to a different model."
        )
    if str(row["status"]) != "pass":
        raise RuntimeError(f"Validation {validation_id} did not pass.")
    if int(row["passed_gates"]) != expected_passes:
        raise RuntimeError(
            f"Validation {validation_id} passed {int(row['passed_gates'])} gates; "
            f"expected {expected_passes}."
        )
    if int(row["failed_gates"]) != 0 or int(row["warning_gates"]) != 0:
        raise RuntimeError(
            f"Validation {validation_id} contains failures or warnings."
        )
    if summary.get("validation_type") != validation_type:
        raise RuntimeError(
            f"Validation {validation_id} type is "
            f"{summary.get('validation_type')!r}; expected {validation_type!r}."
        )
    report = Path(str(row["report_path"] or ""))
    if not report.is_file():
        raise RuntimeError(f"Validation report is missing: {report}")
    return row, summary


def _approval_timestamp(value: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp


def _report_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else settings.project_root / path


def _write_production_report(
    *,
    approval_id: str,
    identity: Any,
    model: dict[str, Any],
    approval: dict[str, Any],
    candidate: pd.Series,
    operational: pd.Series,
    freeze: pd.Series,
    live: pd.Series,
    output_path: Path,
) -> None:
    stable_map = _load_governance()["policy_candidate"]["stable_map"]
    labels = {
        "PAYEMS": "Nonfarm Payroll Change",
        "UNRATE": "Unemployment Rate",
        "CES0500000003": "Average Hourly Earnings Growth",
    }
    stages = [
        ("month_open", "Month open"),
        ("after_week_1", "After week 1"),
        ("after_week_2", "After week 2"),
        ("month_end", "Month end"),
        ("pre_employment_report", "Pre-employment report"),
    ]
    lines = [
        "# MacroPulse Model 1C v1.0.0 Production Approval",
        "",
        f"- Model ID: `{identity.model_id}`",
        f"- Production version: `{identity.model_version}`",
        f"- Lifecycle: `{identity.lifecycle_status}`",
        f"- Promoted from model version: "
        f"`{model.get('validation_source_version')}`",
        f"- Promoted from package version: "
        f"`{model.get('promoted_from_package_version')}`",
        f"- Candidate validation ID: `{candidate['validation_id']}`",
        f"- Candidate validation result: "
        f"**PASS ({int(candidate['passed_gates'])}/39)**",
        f"- Operational validation ID: `{operational['validation_id']}`",
        f"- Operational validation result: "
        f"**PASS ({int(operational['passed_gates'])}/20)**",
        f"- Freeze assessment ID: `{freeze['validation_id']}`",
        f"- Freeze assessment result: "
        f"**PASS ({int(freeze['passed_gates'])}/14)**",
        f"- Governed live run ID: `{live['run_id']}`",
        f"- Approval ID: `{approval_id}`",
        f"- Approved at: `{approval['approved_at']}`",
        f"- Approval phrase: `{approval['approval_phrase']}`",
        f"- Freeze assessment: `{approval['freeze_assessment_report']}`",
        f"- Production configuration hash: `{identity.config_hash}`",
        f"- Production code hash: `{identity.code_hash}`",
        f"- Validated live configuration hash: `{live['config_hash']}`",
        f"- Validated live code hash: `{live['code_hash']}`",
        f"- Validated information-set hash: `{live['information_set_hash']}`",
        f"- Validated model-state hash: `{live['model_state_hash']}`",
        f"- Validated governance signature: `{live['governance_signature']}`",
        "",
        "## Approved production point policy",
        "",
        "| Labour target | Forecast stage | Production component |",
        "|---|---|---|",
    ]
    for target in ["PAYEMS", "UNRATE", "CES0500000003"]:
        for stage, stage_label in stages:
            lines.append(
                f"| {labels[target]} | {stage_label} | "
                f"{stable_map[target][stage]} |"
            )
    lines.extend(
        [
            "",
            "## Approved uncertainty and challenger governance",
            "",
            "- Production interval method: `exp_weighted_q80`.",
            "- Nominal interval coverage: `80%`.",
            "- Minimum prior errors: `24`.",
            "- Rolling calibration window: `48 months`.",
            "- Exponential decay: `0.94`.",
            "- Adaptive selector role: `shadow challenger only`.",
            "",
            "The stable target-stage map controls production headlines. The "
            "adaptive selector cannot replace a production component without a "
            "new version, documented challenger evidence, revalidation, and "
            "explicit model-owner approval.",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def promote_model1c(
    repository: MacroRepository | None = None,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    config = _load_governance()
    model, approval = _approval_config(config)
    identity = current_labour_model_identity()

    if identity.model_id != "US_LABOUR_NOWCAST_1C":
        raise RuntimeError(
            f"Installed model ID is {identity.model_id}; "
            "expected US_LABOUR_NOWCAST_1C."
        )
    if identity.model_version != "1.0.0":
        raise RuntimeError(
            f"Installed Model 1C version is {identity.model_version}; "
            "expected 1.0.0."
        )
    if identity.lifecycle_status != "production":
        raise RuntimeError(
            f"Installed Model 1C lifecycle is {identity.lifecycle_status}; "
            "expected production."
        )

    candidate_id = str(approval["candidate_validation_id"])
    operational_id = str(approval["operational_validation_id"])
    freeze_id = str(approval["freeze_assessment_id"])
    live_run_id = str(approval["governed_live_run_id"])

    candidate, candidate_summary = _validation_row(
        repository,
        candidate_id,
        "candidate_policy",
        EXPECTED_CANDIDATE_PASSES,
    )
    if candidate_summary.get("point_policy") != "stable_candidate":
        raise RuntimeError(
            "Candidate validation does not approve the stable point policy."
        )
    if candidate_summary.get("shadow_policy") != "adaptive_shadow_only":
        raise RuntimeError(
            "Candidate validation does not keep the adaptive selector shadow-only."
        )
    if candidate_summary.get("interval_method") != SELECTED_INTERVAL_METHOD:
        raise RuntimeError(
            "Candidate validation interval method does not match "
            "exp_weighted_q80."
        )

    repair_operational_validation_metadata(repository, operational_id)
    operational, operational_summary = _validation_row(
        repository,
        operational_id,
        "governed_live_operational",
        EXPECTED_OPERATIONAL_PASSES,
    )
    if str(operational_summary.get("live_run_id")) != live_run_id:
        raise RuntimeError(
            "Operational validation is linked to a different governed live run."
        )

    freeze, freeze_summary = _validation_row(
        repository,
        freeze_id,
        "freeze_assessment",
        EXPECTED_FREEZE_PASSES,
    )
    if (
        freeze_summary.get("readiness")
        != "ready_for_model_owner_signoff"
    ):
        raise RuntimeError(
            "Freeze assessment is not ready for model-owner signoff."
        )
    for key, expected in [
        ("candidate_validation_id", candidate_id),
        ("operational_validation_id", operational_id),
        ("live_run_id", live_run_id),
    ]:
        if str(freeze_summary.get(key)) != expected:
            raise RuntimeError(
                f"Freeze assessment {key} does not match the approved "
                "evidence chain."
            )

    live_frame = repository.query_df(
        "SELECT * FROM labour_live_runs WHERE run_id = ?",
        [live_run_id],
    )
    if live_frame.empty:
        raise RuntimeError(
            f"Approved governed live run {live_run_id} is missing."
        )
    live = live_frame.iloc[0]
    if str(live["status"]) != "success":
        raise RuntimeError(
            "Approved governed live run did not complete successfully."
        )
    if str(live["model_version"]) != str(
        model.get("validation_source_version", "0.6.0")
    ):
        raise RuntimeError(
            "Approved governed live run has an unexpected source model version."
        )
    if str(live["candidate_validation_id"]) != candidate_id:
        raise RuntimeError(
            "Approved governed live run is linked to a different "
            "candidate validation."
        )

    forecasts = repository.query_df(
        "SELECT * FROM labour_live_forecasts "
        "WHERE run_id = ? ORDER BY target_series",
        [live_run_id],
    )
    if (
        len(forecasts) != EXPECTED_TARGETS
        or forecasts["target_series"].nunique() != EXPECTED_TARGETS
    ):
        raise RuntimeError(
            "Approved governed live run does not contain three unique "
            "labour headlines."
        )
    stable_map = config["policy_candidate"]["stable_map"]
    violations: list[dict[str, str]] = []
    for row in forecasts.itertuples(index=False):
        expected_model = stable_map[str(row.target_series)][
            str(row.forecast_stage)
        ]
        if str(row.stable_model_name) != str(expected_model):
            violations.append(
                {
                    "target_series": str(row.target_series),
                    "forecast_stage": str(row.forecast_stage),
                    "observed": str(row.stable_model_name),
                    "expected": str(expected_model),
                }
            )
    if violations:
        raise RuntimeError(
            "Approved live run violates the stable production policy: "
            f"{violations}"
        )
    if int(
        (
            forecasts["interval_method"].astype(str)
            != SELECTED_INTERVAL_METHOD
        ).sum()
    ) != 0:
        raise RuntimeError(
            "Approved live run contains an unapproved interval method."
        )
    if (
        forecasts["shadow_model_name"].isna().any()
        or forecasts["shadow_point_forecast"].isna().any()
    ):
        raise RuntimeError(
            "Approved live run does not preserve all adaptive shadow outputs."
        )

    hash_fields = [
        "config_hash",
        "code_hash",
        "information_set_hash",
        "model_state_hash",
        "governance_signature",
    ]
    invalid_hashes = [
        name for name in hash_fields
        if len(str(live.get(name) or "")) != 64
    ]
    if invalid_hashes:
        raise RuntimeError(
            "Approved governed live run has invalid provenance hashes: "
            f"{invalid_hashes}"
        )

    news = repository.query_df(
        "SELECT * FROM labour_news_runs "
        "WHERE current_run_id = ? ORDER BY target_series",
        [live_run_id],
    )
    successful_news = news.loc[
        news["status"].astype(str) == "success"
    ].copy()
    if (
        successful_news["target_series"].nunique()
        != EXPECTED_TARGETS
    ):
        raise RuntimeError(
            "Approved governed live run lacks successful news decomposition "
            "for all targets."
        )
    residual = float(
        pd.to_numeric(
            successful_news["residual_interaction"],
            errors="coerce",
        ).abs().max()
    )
    if (
        not np.isfinite(residual)
        or residual > MAXIMUM_NEWS_RESIDUAL
    ):
        raise RuntimeError(
            f"Approved labour news residual is {residual}; expected "
            f"<= {MAXIMUM_NEWS_RESIDUAL}."
        )

    freeze_relative = Path(
        str(approval["freeze_assessment_report"])
    )
    freeze_report = _report_path(str(freeze_relative))
    if not freeze_report.is_file():
        raise RuntimeError(
            f"Freeze-assessment report not found: {freeze_report}"
        )

    existing = repository.query_df(
        "SELECT * FROM model_approvals "
        "WHERE model_id = ? AND promoted_version = ?",
        [identity.model_id, identity.model_version],
    )
    if not existing.empty:
        existing_row = existing.iloc[0]
        if (
            str(existing_row["approval_phrase"])
            != str(approval["approval_phrase"])
            or str(existing_row["validation_id"]) != freeze_id
            or str(existing_row["decision"])
            != str(approval["decision"])
        ):
            raise RuntimeError(
                "An inconsistent Model 1C v1.0.0 approval already exists."
            )
        approval_id = str(existing_row["approval_id"])
        recorded_at = pd.Timestamp(existing_row["recorded_at"])
    else:
        approval_id = str(uuid.uuid4())
        recorded_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
        approval_row = {
            "approval_id": approval_id,
            "model_id": identity.model_id,
            "promoted_version": identity.model_version,
            "source_model_version": str(
                model.get("validation_source_version", "0.6.0")
            ),
            "source_package_version": str(
                model.get(
                    "promoted_from_package_version",
                    "0.6.0.post1",
                )
            ),
            "validation_id": freeze_id,
            "validation_status": "pass",
            "decision": str(approval["decision"]),
            "approval_phrase": str(approval["approval_phrase"]),
            "approved_at": _approval_timestamp(
                str(approval["approved_at"])
            ),
            "freeze_assessment_report": str(
                freeze_relative
            ).replace("/", "\\"),
            "recorded_at": recorded_at,
            "notes": (
                f"Model 1C v1.0.0 production approval. Candidate validation "
                f"{candidate_id}; operational validation {operational_id}; "
                f"freeze assessment {freeze_id}. Stable target-stage map is "
                "production; adaptive selector remains shadow-only."
            ),
        }
        repository.register_model_approval(approval_row)

    repository.register_model_identity(
        identity.as_dict(),
        notes=(
            "Production promotion from Model 1C "
            f"{model.get('validation_source_version')}; freeze assessment "
            f"{freeze_id}; approval {approval_id}."
        ),
    )

    output_path = (
        settings.project_root
        / "reports"
        / "production"
        / "model1c_v1_0_0_production_approval.md"
    )
    _write_production_report(
        approval_id=approval_id,
        identity=identity,
        model=model,
        approval=approval,
        candidate=candidate,
        operational=operational,
        freeze=freeze,
        live=live,
        output_path=output_path,
    )

    return {
        "approval_id": approval_id,
        "model_id": identity.model_id,
        "production_version": identity.model_version,
        "source_version": str(
            model.get("validation_source_version", "0.6.0")
        ),
        "candidate_validation_id": candidate_id,
        "operational_validation_id": operational_id,
        "freeze_assessment_id": freeze_id,
        "live_run_id": live_run_id,
        "report_path": output_path,
        "config_hash": identity.config_hash,
        "code_hash": identity.code_hash,
        "recorded_at": recorded_at,
    }
