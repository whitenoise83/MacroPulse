from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.prospective_shadow import month_end, prospective_shadow_plan
from macropulse.macro_state.prospective_shadow_service import (
    run_macro_state_prospective_shadow,
)
from macropulse.macro_state.shadow_outcomes_service import (
    resolve_macro_state_shadow_outcomes,
)
from macropulse.macro_state.versioning import load_macro_state_governance
from macropulse.operations.model1d_shadow_monitoring import run_shadow_monitoring
from macropulse.settings import settings


def run_monthly_shadow_operations(
    repository: MacroRepository | None = None,
    *,
    as_of: date | None = None,
    project_root: Path | None = None,
    create_prediction: bool = True,
    resolve_outcomes: bool = True,
    write_report: bool = True,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    root = Path(project_root or settings.project_root)
    operation_as_of = as_of or date.today()
    if operation_as_of > date.today():
        raise ValueError("The operational cutoff cannot be in the future.")

    config = load_macro_state_governance(root)
    plan = prospective_shadow_plan(config)
    state_date = month_end(operation_as_of)
    existing = repository.query_df(
        """
        SELECT shadow_run_id, state_date, information_cutoff, status
        FROM macro_state_shadow_runs
        WHERE model_version = ? AND state_date = ?
        ORDER BY created_at
        """,
        [plan.model_version, state_date],
    )

    prediction_result: dict[str, Any] | None = None
    prediction_action = "disabled"
    shadow_run_id: str | None = None
    if create_prediction:
        if existing.empty:
            prediction_result = run_macro_state_prospective_shadow(
                repository=repository,
                as_of=operation_as_of,
                project_root=root,
            )
            prediction_action = "created"
            shadow_run_id = str(prediction_result["shadow_run_id"])
        else:
            prediction_action = "skipped_existing_month"
            shadow_run_id = str(existing.iloc[0]["shadow_run_id"])
    elif not existing.empty:
        shadow_run_id = str(existing.iloc[0]["shadow_run_id"])

    resolution_result: dict[str, Any] | None = None
    if resolve_outcomes:
        resolution_result = resolve_macro_state_shadow_outcomes(
            repository=repository,
            as_of=operation_as_of,
            project_root=root,
        )

    monitoring_result = run_shadow_monitoring(
        repository=repository,
        as_of=operation_as_of,
        project_root=root,
        write_report=write_report,
    )
    readiness = monitoring_result["readiness"].iloc[0]
    return {
        "operation_as_of": operation_as_of,
        "state_date": state_date,
        "model_version": plan.model_version,
        "prediction_action": prediction_action,
        "shadow_run_id": shadow_run_id,
        "prediction_result": prediction_result,
        "resolution_result": resolution_result,
        "resolved_runs": (
            int(resolution_result["resolved_runs"])
            if resolution_result is not None
            else 0
        ),
        "unresolved_runs": (
            int(resolution_result["unresolved_runs"])
            if resolution_result is not None
            else 0
        ),
        "outcome_rows_appended": (
            int(resolution_result["outcome_rows_appended"])
            if resolution_result is not None
            else 0
        ),
        "complete_target_months": int(readiness["complete_target_months"]),
        "minimum_complete_target_months": int(
            readiness["minimum_complete_target_months"]
        ),
        "comparison_permitted": bool(readiness["comparison_permitted"]),
        "promotion_authority": str(readiness["promotion_authority"]),
        "integrity_pass": bool(readiness["integrity_pass"]),
        "monitoring": monitoring_result,
        "output_paths": monitoring_result["output_paths"],
    }
