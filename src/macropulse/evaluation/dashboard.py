from __future__ import annotations

import json
from typing import Any

import pandas as pd


def current_forecast_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("current_forecasts", []) or []
    return pd.DataFrame(rows)


def evidence_flag_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("evidence_flags", []) or []
    return pd.DataFrame(rows)


def performance_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("performance", {}).get("target_metrics", []) or []
    return pd.DataFrame(rows)


def drift_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("performance", {}).get("drift_metrics", []) or []
    return pd.DataFrame(rows)


def comparable_revision_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("revisions", {}).get("revisions", []) or []
    frame = pd.DataFrame(rows)
    if frame.empty or "comparison_status" not in frame.columns:
        return frame
    return frame.loc[
        frame["comparison_status"].astype(str).eq("comparable_revision")
    ].reset_index(drop=True)


def release_event_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("revisions", {}).get("release_events", []) or []
    return pd.DataFrame(rows)


def upcoming_release_table(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = snapshot.get("calendar", {}).get("upcoming_releases", []) or []
    return pd.DataFrame(rows)


def model1d_research_summary(snapshot: dict[str, Any]) -> pd.DataFrame:
    evidence = snapshot.get("model1d_research", {}).get("evidence", {}) or {}
    run = evidence.get("run") or {}
    component = evidence.get("component") or {}
    detail = evidence.get("status_detail") or {}
    if not run and not component and not detail:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "model_id": run.get("model_id") or component.get("model_id"),
                "model_version": (
                    run.get("model_version")
                    or component.get("model_version")
                ),
                "state_date": run.get("state_date"),
                "information_cutoff": run.get("information_cutoff"),
                "status": run.get("status") or component.get("freshness_state"),
                "complete_target_months": detail.get(
                    "complete_target_months"
                ),
                "outcome_count": detail.get("outcome_count"),
                "promotion_authority": "none",
            }
        ]
    )


def snapshot_download_bytes(snapshot: dict[str, Any]) -> bytes:
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
