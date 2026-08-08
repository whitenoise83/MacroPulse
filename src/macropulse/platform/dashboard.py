from __future__ import annotations

from typing import Any

import pandas as pd


COMPONENT_ORDER = ("1A", "1B", "1C", "1D")


def component_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for component in COMPONENT_ORDER:
        if component == "1D":
            summary = snapshot.get("model1d", {}).get("component", {}) or {}
        else:
            summary = (
                snapshot.get("production", {})
                .get(component, {})
                .get("component", {})
                or {}
            )
        rows.append(
            {
                "component": component,
                "model_id": summary.get("model_id"),
                "version": summary.get("model_version"),
                "lifecycle": summary.get("lifecycle_status"),
                "state": summary.get("freshness_state"),
                "information_cutoff": summary.get("information_cutoff"),
                "data_as_of": summary.get("data_as_of"),
                "target_period": summary.get("target_period"),
                "ready": bool(summary.get("ready", False)),
                "stale_sources": int(summary.get("stale_source_count", 0) or 0),
            }
        )
    return pd.DataFrame(rows)


def forecast_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for component in ("1A", "1B", "1C"):
        block = snapshot.get("production", {}).get(component, {})
        for row in block.get("forecasts", []) or []:
            rows.append(
                {
                    "component": component,
                    "target": row.get("target_name"),
                    "series": row.get("target_series"),
                    "target_period": row.get("target_period"),
                    "stage": row.get("forecast_stage"),
                    "model": row.get("stable_model_name"),
                    "forecast": row.get("stable_point_forecast"),
                    "lower_80": row.get("lower_80"),
                    "upper_80": row.get("upper_80"),
                }
            )
    return pd.DataFrame(rows)


def change_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    changes = snapshot.get("changes_since_previous_governed_run", {})
    for component in ("1A", "1B", "1C"):
        for row in changes.get(component, []) or []:
            rows.append(
                {
                    "component": component,
                    "target": row.get("target_name"),
                    "current_period": row.get("current_target_period"),
                    "previous_period": row.get("previous_target_period"),
                    "current_forecast": row.get("current_forecast"),
                    "previous_forecast": row.get("previous_forecast"),
                    "forecast_change": row.get("forecast_change"),
                    "comparable": bool(row.get("comparable_forecast", False)),
                    "target_period_changed": bool(
                        row.get("target_period_changed", False)
                    ),
                    "stage_changed": bool(row.get("stage_changed", False)),
                    "current_stage": row.get("current_stage"),
                    "previous_stage": row.get("previous_stage"),
                }
            )
    return pd.DataFrame(rows)


def model1d_prediction_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("model1d", {}).get("predictions", []) or []
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def model1d_dimension_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("model1d", {}).get("dimensions", []) or []
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def source_health_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("freshness", {}).get("source_health", []) or []
    return pd.DataFrame(rows)


def due_release_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("freshness", {}).get("due_releases", []) or []
    return pd.DataFrame(rows)


def upcoming_release_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("calendar", {}).get("upcoming_releases", []) or []
    return pd.DataFrame(rows)


def provenance_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for component in ("1A", "1B", "1C"):
        item = snapshot.get("provenance", {}).get(component, {}) or {}
        if not item:
            continue
        rows.append({"component": component, **item})

    model1d_run = snapshot.get("model1d", {}).get("run") or {}
    if model1d_run:
        rows.append(
            {
                "component": "1D",
                "run_id": model1d_run.get("shadow_run_id"),
                "model_id": model1d_run.get("model_id"),
                "model_version": model1d_run.get("model_version"),
                "information_cutoff": model1d_run.get("information_cutoff"),
                "data_as_of": model1d_run.get("state_date"),
                "status": model1d_run.get("status"),
                "config_hash": model1d_run.get("config_hash"),
                "code_hash": model1d_run.get("code_hash"),
                "git_commit": model1d_run.get("git_commit"),
                "information_set_hash": model1d_run.get(
                    "information_set_hash"
                ),
                "model_state_hash": None,
                "governance_signature": None,
                "source_bundle_hash": model1d_run.get("source_bundle_hash"),
            }
        )
    return pd.DataFrame(rows)


def snapshot_download_bytes(snapshot: dict[str, Any]) -> bytes:
    import json

    return (
        json.dumps(
            snapshot,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
