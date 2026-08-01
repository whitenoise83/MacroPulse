from __future__ import annotations

import json
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository

MODEL_ID = "US_LABOUR_NOWCAST_1C"
OPERATIONAL_TYPE = "governed_live_operational"


def _json_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def repair_operational_validation_metadata(
    repository: MacroRepository,
    validation_id: str,
) -> dict[str, Any]:
    frame = repository.query_df(
        """
        SELECT validation_id, backtest_id, model_id, model_version,
               status, passed_gates, failed_gates, warning_gates,
               summary_json
        FROM labour_validation_runs
        WHERE validation_id = ?
        """,
        [validation_id],
    )
    if frame.empty:
        raise RuntimeError(
            f"Operational validation ID {validation_id} is not present in DuckDB."
        )

    row = frame.iloc[0]
    summary = _json_mapping(row["summary_json"])
    if summary.get("validation_type") != OPERATIONAL_TYPE:
        raise RuntimeError(
            f"Validation {validation_id} is not a governed-live operational validation."
        )

    live_run_id = str(summary.get("live_run_id") or "")
    if not live_run_id:
        raise RuntimeError(
            f"Validation {validation_id} does not record a governed live run ID."
        )

    live_frame = repository.query_df(
        """
        SELECT run_id, model_id, model_version, backtest_id, status
        FROM labour_live_runs
        WHERE run_id = ?
        """,
        [live_run_id],
    )
    if live_frame.empty:
        raise RuntimeError(
            f"Linked governed live run {live_run_id} is not present in DuckDB."
        )
    live = live_frame.iloc[0]
    expected = {
        "backtest_id": str(live["backtest_id"]),
        "model_id": str(live["model_id"]),
        "model_version": str(live["model_version"]),
    }
    observed = {
        "backtest_id": str(row["backtest_id"]),
        "model_id": str(row["model_id"]),
        "model_version": str(row["model_version"]),
    }

    if expected["model_id"] != MODEL_ID:
        raise RuntimeError(
            f"Linked live run belongs to {expected['model_id']}, not {MODEL_ID}."
        )

    if observed == expected:
        return {
            "validation_id": validation_id,
            "live_run_id": live_run_id,
            "status": "already_correct",
            "before": observed,
            "after": expected,
        }

    legacy_shift = (
        observed["backtest_id"] == expected["model_id"]
        and observed["model_id"] == expected["model_version"]
        and observed["model_version"] == expected["backtest_id"]
    )
    if not legacy_shift:
        raise RuntimeError(
            "The validation metadata differs from the linked live run, but it does "
            "not match the known legacy three-column ordering defect. No automatic "
            f"change was made. Observed={observed}; expected={expected}"
        )

    with repository.connect() as connection:
        connection.execute(
            """
            UPDATE labour_validation_runs
            SET backtest_id = ?, model_id = ?, model_version = ?
            WHERE validation_id = ?
            """,
            [
                expected["backtest_id"],
                expected["model_id"],
                expected["model_version"],
                validation_id,
            ],
        )

    verification = repository.query_df(
        """
        SELECT backtest_id, model_id, model_version
        FROM labour_validation_runs
        WHERE validation_id = ?
        """,
        [validation_id],
    ).iloc[0]
    after = {
        "backtest_id": str(verification["backtest_id"]),
        "model_id": str(verification["model_id"]),
        "model_version": str(verification["model_version"]),
    }
    if after != expected:
        raise RuntimeError(
            f"Operational validation metadata repair did not verify: {after}"
        )

    return {
        "validation_id": validation_id,
        "live_run_id": live_run_id,
        "status": "repaired",
        "before": observed,
        "after": after,
    }
