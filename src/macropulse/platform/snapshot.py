from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.platform.status import collect_platform_status, serialise_platform_status


SNAPSHOT_SCHEMA_VERSION = "1.0.0"
PRODUCTION_COMPONENTS = ("1A", "1B", "1C")
StatusProvider = Callable[[MacroRepository, date, Path], dict[str, Any]]


def _normalise(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {
            str(key): _normalise(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if isinstance(value, (date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        missing = False
    if isinstance(missing, bool) and missing:
        return None
    return value


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        _normalise(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def semantic_snapshot_hash(payload_without_hash: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload_without_hash)).hexdigest()


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    records = frame.where(pd.notna(frame), None).to_dict("records")
    return [_normalise(record) for record in records]


def _component_map(status: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["component"]): row
        for row in _records(status["components"])
    }


def _previous_run_id(
    repository: MacroRepository,
    *,
    component: str,
    model_id: str,
    model_version: str,
    current_run_id: str,
    as_of: date,
) -> str | None:
    if component == "1A":
        frame = repository.query_df(
            """
            SELECT run_id
            FROM forecast_registry
            WHERE model_id = ?
              AND model_version = ?
              AND status = 'success'
              AND information_cutoff <= ?
              AND run_id <> ?
            ORDER BY information_cutoff DESC, created_at DESC
            LIMIT 1
            """,
            [model_id, model_version, as_of, current_run_id],
        )
    else:
        table = "inflation_live_runs" if component == "1B" else "labour_live_runs"
        frame = repository.query_df(
            f"""
            SELECT run_id
            FROM {table}
            WHERE model_id = ?
              AND model_version = ?
              AND status = 'success'
              AND information_cutoff <= ?
              AND run_id <> ?
            ORDER BY information_cutoff DESC, run_timestamp DESC
            LIMIT 1
            """,
            [model_id, model_version, as_of, current_run_id],
        )
    return None if frame.empty else str(frame.iloc[0]["run_id"])


def _gdp_forecast(repository: MacroRepository, run_id: str) -> pd.DataFrame:
    return repository.query_df(
        """
        SELECT
            run_id,
            target_period,
            forecast_stage,
            champion_model AS stable_model_name,
            production_forecast AS stable_point_forecast,
            lower_80,
            upper_80
        FROM forecast_registry
        WHERE run_id = ?
        """,
        [run_id],
    )


def _live_forecasts(
    repository: MacroRepository,
    *,
    component: str,
    run_id: str,
) -> pd.DataFrame:
    table = "inflation_live_forecasts" if component == "1B" else "labour_live_forecasts"
    unit_column = (
        "CAST(NULL AS VARCHAR) AS target_unit,"
        if component == "1B"
        else "target_unit,"
    )
    return repository.query_df(
        f"""
        SELECT
            run_id,
            target_series,
            target_name,
            {unit_column}
            target_period,
            forecast_stage,
            stable_model_name,
            stable_point_forecast,
            lower_80,
            upper_80,
            shadow_model_name,
            shadow_point_forecast
        FROM {table}
        WHERE run_id = ?
        ORDER BY target_series
        """,
        [run_id],
    )


def _production_forecast_records(
    repository: MacroRepository,
    *,
    component: str,
    run_id: str,
) -> list[dict[str, Any]]:
    if component == "1A":
        frame = _gdp_forecast(repository, run_id)
        if frame.empty:
            return []
        row = _records(frame)[0]
        return [{
            "target_series": "GDPC1",
            "target_name": "Real GDP Growth",
            "target_unit": "annualised percent",
            "target_period": row["target_period"],
            "forecast_stage": row["forecast_stage"],
            "stable_model_name": row["stable_model_name"],
            "stable_point_forecast": row["stable_point_forecast"],
            "lower_80": row["lower_80"],
            "upper_80": row["upper_80"],
            "shadow_model_name": None,
            "shadow_point_forecast": None,
        }]
    return _records(
        _live_forecasts(repository, component=component, run_id=run_id)
    )


def _forecast_changes(
    current: list[dict[str, Any]],
    previous: list[dict[str, Any]],
    *,
    current_run_id: str,
    previous_run_id: str | None,
) -> list[dict[str, Any]]:
    previous_by_target = {
        str(row["target_series"]): row
        for row in previous
    }
    changes: list[dict[str, Any]] = []
    for row in current:
        target = str(row["target_series"])
        old = previous_by_target.get(target)
        same_period = bool(
            old is not None
            and str(old.get("target_period")) == str(row.get("target_period"))
        )
        current_value = row.get("stable_point_forecast")
        previous_value = old.get("stable_point_forecast") if old else None
        delta = None
        if same_period and current_value is not None and previous_value is not None:
            delta = float(current_value) - float(previous_value)
        changes.append({
            "target_series": target,
            "target_name": row.get("target_name"),
            "current_run_id": current_run_id,
            "previous_run_id": previous_run_id,
            "current_target_period": row.get("target_period"),
            "previous_target_period": old.get("target_period") if old else None,
            "target_period_changed": bool(old is not None and not same_period),
            "comparable_forecast": same_period,
            "previous_forecast": previous_value if same_period else None,
            "current_forecast": current_value,
            "forecast_change": delta,
            "previous_stage": old.get("forecast_stage") if old else None,
            "current_stage": row.get("forecast_stage"),
            "stage_changed": bool(
                old is not None
                and old.get("forecast_stage") != row.get("forecast_stage")
            ),
        })
    return changes


def _provenance_1a(repository: MacroRepository, run_id: str) -> dict[str, Any]:
    frame = repository.query_df(
        """
        SELECT
            run_id, model_id, model_version, config_hash, code_hash, git_commit,
            information_set_hash, information_cutoff, data_as_of, target_period,
            forecast_stage, status
        FROM forecast_registry
        WHERE run_id = ?
        """,
        [run_id],
    )
    return _records(frame)[0] if not frame.empty else {}


def _provenance_live(
    repository: MacroRepository,
    *,
    component: str,
    run_id: str,
) -> dict[str, Any]:
    table = "inflation_live_runs" if component == "1B" else "labour_live_runs"
    frame = repository.query_df(
        f"""
        SELECT
            run_id, model_id, model_version, information_cutoff, data_as_of,
            status, candidate_validation_id, backtest_id, config_hash, code_hash,
            git_commit, information_set_hash, model_state_hash,
            governance_signature
        FROM {table}
        WHERE run_id = ?
        """,
        [run_id],
    )
    return _records(frame)[0] if not frame.empty else {}


def _model1d_snapshot(
    repository: MacroRepository,
    *,
    run_id: str | None,
) -> dict[str, Any]:
    if not run_id:
        return {"run": None, "predictions": [], "dimensions": []}

    run = repository.query_df(
        """
        SELECT
            shadow_run_id, model_id, model_version, state_date,
            information_cutoff, target_mode, target_horizon_days,
            target_expected_available_date, source_candidate_id,
            source_evidence_version, primary_comparator,
            source_macro_state_run_id, gdp_run_id, inflation_run_id,
            labour_run_id, config_hash, code_hash, git_commit,
            information_set_hash, source_bundle_hash, no_look_ahead_pass,
            status
        FROM macro_state_shadow_runs
        WHERE shadow_run_id = ?
        """,
        [run_id],
    )
    predictions = repository.query_df(
        """
        SELECT
            benchmark_id, predicted_family, predicted_probabilities_json,
            top1_family, top2_family, top3_family,
            top1_probability, top2_probability, top3_probability,
            top1_top2_gap, entropy, probability_sum,
            probability_vector_hash, no_look_ahead_pass
        FROM macro_state_shadow_predictions
        WHERE shadow_run_id = ?
        ORDER BY benchmark_id
        """,
        [run_id],
    )
    dimensions = repository.query_df(
        """
        SELECT
            dimension, score, lower_score, upper_score, label, confidence,
            source_model_id, source_model_version, source_run_id,
            source_information_cutoff, source_data_as_of, source_hash,
            no_look_ahead_pass
        FROM macro_state_shadow_dimensions
        WHERE shadow_run_id = ?
        ORDER BY dimension
        """,
        [run_id],
    )

    prediction_records = _records(predictions)
    for row in prediction_records:
        raw = row.get("predicted_probabilities_json")
        row["predicted_probabilities"] = (
            _normalise(json.loads(raw))
            if isinstance(raw, str)
            else None
        )
        row.pop("predicted_probabilities_json", None)

    return {
        "run": _records(run)[0] if not run.empty else None,
        "predictions": prediction_records,
        "dimensions": _records(dimensions),
    }


def build_macro_snapshot(
    repository: MacroRepository,
    *,
    as_of: date,
    project_root: Path,
    status_provider: StatusProvider = collect_platform_status,
) -> dict[str, Any]:
    if as_of > date.today():
        raise ValueError("Snapshot as-of date cannot be in the future.")

    status = status_provider(
        repository,
        as_of=as_of,
        project_root=project_root,
    )
    status_json = serialise_platform_status(status)
    components = _component_map(status)

    production: dict[str, Any] = {}
    changes: dict[str, Any] = {}
    provenance: dict[str, Any] = {}

    for component in PRODUCTION_COMPONENTS:
        summary = components.get(component, {})
        current_run_id = summary.get("run_id")
        if current_run_id is None:
            production[component] = {
                "component": summary,
                "forecasts": [],
                "previous_run_id": None,
            }
            changes[component] = []
            provenance[component] = {}
            continue

        current_run_id = str(current_run_id)
        previous_run_id = _previous_run_id(
            repository,
            component=component,
            model_id=str(summary["model_id"]),
            model_version=str(summary["model_version"]),
            current_run_id=current_run_id,
            as_of=as_of,
        )
        current_forecasts = _production_forecast_records(
            repository,
            component=component,
            run_id=current_run_id,
        )
        previous_forecasts = (
            _production_forecast_records(
                repository,
                component=component,
                run_id=previous_run_id,
            )
            if previous_run_id
            else []
        )
        production[component] = {
            "component": summary,
            "forecasts": current_forecasts,
            "previous_run_id": previous_run_id,
        }
        changes[component] = _forecast_changes(
            current_forecasts,
            previous_forecasts,
            current_run_id=current_run_id,
            previous_run_id=previous_run_id,
        )
        provenance[component] = (
            _provenance_1a(repository, current_run_id)
            if component == "1A"
            else _provenance_live(
                repository,
                component=component,
                run_id=current_run_id,
            )
        )

    model1d_summary = components.get("1D", {})
    model1d_run_id = model1d_summary.get("run_id")
    model1d = {
        "component": model1d_summary,
        "status_detail": (
            status_json["model1d"][0]
            if status_json.get("model1d")
            else None
        ),
        **_model1d_snapshot(
            repository,
            run_id=str(model1d_run_id) if model1d_run_id else None,
        ),
    }

    readiness = (
        status_json["readiness"][0]
        if status_json.get("readiness")
        else {}
    )

    semantic_payload = _normalise({
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "as_of": as_of.isoformat(),
        "contract": {
            "database_access": "read_only",
            "model_execution": "none",
            "data_download": "none",
            "semantic_hash_excludes_export_path_and_wall_clock": True,
        },
        "readiness": readiness,
        "production": production,
        "changes_since_previous_governed_run": changes,
        "model1d": model1d,
        "freshness": {
            "source_health": status_json.get("source_health", []),
            "due_releases": status_json.get("due_releases", []),
        },
        "calendar": {
            "upcoming_releases": status_json.get("upcoming_releases", []),
        },
        "provenance": provenance,
    })
    return {
        **semantic_payload,
        "snapshot_hash": semantic_snapshot_hash(semantic_payload),
    }


def write_macro_snapshot(
    snapshot: dict[str, Any],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            _normalise(snapshot),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output_path
