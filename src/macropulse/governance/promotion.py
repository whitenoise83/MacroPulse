from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.governance.versioning import current_model_identity, load_governance_config
from macropulse.settings import settings


def _approval_config() -> dict[str, Any]:
    governance = load_governance_config()
    model = governance.get("model", {})
    approval = model.get("approval", {})
    if not isinstance(approval, dict) or approval.get("status") != "approved":
        raise RuntimeError("Model-owner approval is not recorded in model_governance.yml.")
    return {"model": model, "approval": approval}


def promote_model1a(repository: MacroRepository | None = None) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    identity = current_model_identity()
    configured = _approval_config()
    model = configured["model"]
    approval = configured["approval"]

    if identity.model_version != "1.0.0":
        raise RuntimeError(
            f"Installed model version is {identity.model_version}; expected 1.0.0."
        )
    if identity.lifecycle_status != "production":
        raise RuntimeError(
            f"Lifecycle is {identity.lifecycle_status}; expected production."
        )

    validation_id = str(approval["validation_id"])
    source_version = str(model.get("validation_source_version", "0.6.1"))
    source_package_version = str(model.get("promoted_from_package_version", ""))

    validation = repository.query_df(
        """
        SELECT validation_id, model_id, model_version, status, passed_gates,
               total_gates, report_path
        FROM validation_runs
        WHERE validation_id = ?
        """,
        [validation_id],
    )
    if validation.empty:
        raise RuntimeError(
            f"Approved validation ID {validation_id} is not present in DuckDB."
        )
    row = validation.iloc[0]
    if str(row["model_id"]) != identity.model_id:
        raise RuntimeError("Approved validation belongs to a different model ID.")
    if str(row["model_version"]) != source_version:
        raise RuntimeError(
            f"Approved validation version is {row['model_version']}; expected {source_version}."
        )
    if str(row["status"]) != "pass":
        raise RuntimeError("Approved validation status is not pass.")
    if int(row["passed_gates"]) != int(row["total_gates"]):
        raise RuntimeError("Approved validation did not pass every gate.")

    attention = repository.query_df(
        """
        SELECT status, COUNT(*) AS records
        FROM validation_checks
        WHERE validation_id = ? AND status IN ('fail', 'warning')
        GROUP BY status
        """,
        [validation_id],
    )
    if not attention.empty:
        raise RuntimeError(
            "Approved validation still contains failed or warning checks: "
            + attention.to_dict(orient="records").__repr__()
        )

    stage_history = repository.query_df(
        """
        SELECT stage_backtest_id, status
        FROM stage_backtest_runs
        WHERE model_id = ? AND model_version = ?
          AND status IN ('success', 'partial')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [identity.model_id, source_version],
    )
    if stage_history.empty:
        raise RuntimeError(
            f"No staged validation history exists for source version {source_version}."
        )

    live_source = repository.query_df(
        """
        SELECT COUNT(*) AS records
        FROM forecast_registry
        WHERE model_id = ? AND model_version = ?
        """,
        [identity.model_id, source_version],
    )
    if int(live_source.iloc[0]["records"]) < 1:
        raise RuntimeError(
            f"No governed live forecast exists for source version {source_version}."
        )

    freeze_relative = Path(str(approval["freeze_assessment_report"]))
    freeze_path = settings.project_root / freeze_relative
    if not freeze_path.exists():
        raise RuntimeError(f"Freeze-assessment report not found: {freeze_path}")

    approved_at = pd.Timestamp(str(approval["approved_at"]))
    if approved_at.tzinfo is not None:
        approved_at = approved_at.tz_convert("UTC").tz_localize(None)
    recorded_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    approval_id = str(uuid.uuid4())
    approval_row = {
        "approval_id": approval_id,
        "model_id": identity.model_id,
        "promoted_version": identity.model_version,
        "source_model_version": source_version,
        "source_package_version": source_package_version,
        "validation_id": validation_id,
        "validation_status": str(row["status"]),
        "decision": str(approval["decision"]),
        "approval_phrase": str(approval["approval_phrase"]),
        "approved_at": approved_at,
        "freeze_assessment_report": str(freeze_relative).replace("/", "\\"),
        "recorded_at": recorded_at,
        "notes": (
            "Model-owner approval promoted the validated Stable Stage Policy to "
            "Model 1A v1.0.0 production. Robust Stage-Adaptive Policy remains shadow-only."
        ),
    }

    repository.register_model_identity(
        identity.as_dict(),
        notes=(
            f"Production promotion from validated model version {source_version}; "
            f"validation ID {validation_id}; approval ID {approval_id}."
        ),
    )
    repository.register_model_approval(approval_row)

    output_dir = settings.project_root / "reports" / "production"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "model1a_v1_0_0_production_approval.md"
    lines = [
        "# MacroPulse Model 1A v1.0.0 Production Approval",
        "",
        f"- Model ID: `{identity.model_id}`",
        f"- Production version: `{identity.model_version}`",
        f"- Lifecycle: `{identity.lifecycle_status}`",
        f"- Promoted from model version: `{source_version}`",
        f"- Promoted from package version: `{source_package_version}`",
        f"- Validation ID: `{validation_id}`",
        f"- Validation result: **PASS ({int(row['passed_gates'])}/{int(row['total_gates'])})**",
        f"- Approval ID: `{approval_id}`",
        f"- Approved at: `{approval['approved_at']}`",
        f"- Approval phrase: `{approval['approval_phrase']}`",
        f"- Freeze assessment: `{freeze_relative.as_posix()}`",
        f"- Configuration hash: `{identity.config_hash}`",
        f"- Code hash: `{identity.code_hash}`",
        "",
        "## Approved production policy",
        "",
        "| Forecast stage | Production component |",
        "|---|---|",
        "| Early quarter | Dynamic Factor Model |",
        "| After month 1 | Dynamic Factor Model |",
        "| After month 2 | Fixed Bridge-DFM Ensemble |",
        "| Quarter end | Rolling Bridge-DFM Ensemble |",
        "| Pre-advance release | Dynamic Factor Model |",
        "",
        "The Robust Stage-Adaptive Policy remains a shadow challenger. Future model "
        "changes require a new version, documented challenger evidence, and revalidation.",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "approval_id": approval_id,
        "model_id": identity.model_id,
        "production_version": identity.model_version,
        "source_version": source_version,
        "validation_id": validation_id,
        "validation_passed": int(row["passed_gates"]),
        "validation_total": int(row["total_gates"]),
        "stage_backtest_id": str(stage_history.iloc[0]["stage_backtest_id"]),
        "report_path": output_path,
        "config_hash": identity.config_hash,
        "code_hash": identity.code_hash,
    }
