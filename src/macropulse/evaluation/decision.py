from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.evaluation.ledger import (
    build_forecast_evaluation_ledger,
    serialise_forecast_evaluation,
)
from macropulse.evaluation.performance import serialise_performance_report
from macropulse.evaluation.revisions import (
    build_revision_release_analytics,
    serialise_revision_release_analytics,
)
from macropulse.platform.snapshot import (
    build_macro_snapshot,
    semantic_snapshot_hash,
)


DECISION_INTELLIGENCE_SCHEMA_VERSION = "1.0.0"

MacroSnapshotProvider = Callable[..., dict[str, Any]]
LedgerProvider = Callable[..., pd.DataFrame]
RevisionProvider = Callable[..., dict[str, pd.DataFrame]]


def _metric_map(
    performance: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row["component"]), str(row["target_series"])): row
        for row in performance.get("target_metrics", [])
    }


def _drift_map(
    performance: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row["component"]), str(row["target_series"])): row
        for row in performance.get("drift_metrics", [])
    }


def _latest_revision_map(
    revisions: dict[str, Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in revisions.get("revisions", []):
        key = (
            str(row["component"]),
            str(row["target_series"]),
            str(row["target_period"]),
        )
        current = result.get(key)
        if current is None:
            result[key] = row
            continue
        current_cutoff = str(current.get("current_information_cutoff") or "")
        candidate_cutoff = str(row.get("current_information_cutoff") or "")
        if candidate_cutoff > current_cutoff:
            result[key] = row
    return result


def _ledger_current_map(
    evaluation: dict[str, Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in evaluation.get("ledger", []):
        key = (
            str(row["component"]),
            str(row["target_series"]),
            str(row["target_period"]),
        )
        current = result.get(key)
        if current is None:
            result[key] = row
            continue
        current_cutoff = str(current.get("information_cutoff") or "")
        candidate_cutoff = str(row.get("information_cutoff") or "")
        if candidate_cutoff > current_cutoff:
            result[key] = row
            continue
        if candidate_cutoff == current_cutoff:
            if str(row.get("run_id") or "") > str(current.get("run_id") or ""):
                result[key] = row
    return result


def build_current_forecast_evidence(
    *,
    platform_snapshot: dict[str, Any],
    evaluation: dict[str, Any],
    performance: dict[str, Any],
    revisions: dict[str, Any],
) -> list[dict[str, Any]]:
    metrics = _metric_map(performance)
    drift = _drift_map(performance)
    revision_map = _latest_revision_map(revisions)
    ledger_map = _ledger_current_map(evaluation)

    records: list[dict[str, Any]] = []
    for component in ("1A", "1B", "1C"):
        block = platform_snapshot.get("production", {}).get(component, {}) or {}
        summary = block.get("component", {}) or {}
        for forecast in block.get("forecasts", []) or []:
            target_series = str(forecast.get("target_series"))
            target_period = str(forecast.get("target_period"))
            key2 = (component, target_series)
            key3 = (component, target_series, target_period)

            metric = metrics.get(key2, {})
            drift_row = drift.get(key2, {})
            revision = revision_map.get(key3, {})
            ledger_row = ledger_map.get(key3, {})

            historical_status = metric.get("sample_status")
            if historical_status is None:
                historical_status = "no_resolved_history"

            records.append(
                {
                    "component": component,
                    "model_id": summary.get("model_id"),
                    "model_version": summary.get("model_version"),
                    "run_id": summary.get("run_id"),
                    "information_cutoff": summary.get("information_cutoff"),
                    "data_as_of": summary.get("data_as_of"),
                    "freshness_state": summary.get("freshness_state"),
                    "ready": bool(summary.get("ready", False)),
                    "target_series": target_series,
                    "target_name": forecast.get("target_name"),
                    "target_period": target_period,
                    "forecast_stage": forecast.get("forecast_stage"),
                    "forecast_value": forecast.get("stable_point_forecast"),
                    "lower_80": forecast.get("lower_80"),
                    "upper_80": forecast.get("upper_80"),
                    "estimated_release_date": ledger_row.get(
                        "estimated_release_date"
                    ),
                    "evaluation_status": ledger_row.get("evaluation_status"),
                    "outcome_vintage": ledger_row.get("outcome_vintage"),
                    "recent_revision": revision.get("revision"),
                    "recent_revision_direction": revision.get(
                        "revision_direction"
                    ),
                    "previous_information_cutoff": revision.get(
                        "previous_information_cutoff"
                    ),
                    "previous_forecast_value": revision.get(
                        "previous_forecast_value"
                    ),
                    "associated_release_count": int(
                        revision.get("associated_release_count", 0) or 0
                    ),
                    "advanced_source_release_count": int(
                        revision.get("advanced_source_release_count", 0) or 0
                    ),
                    "release_association_state": revision.get(
                        "release_association_state"
                    ),
                    "n_resolved_history": int(
                        metric.get("n_resolved", 0) or 0
                    ),
                    "historical_context_status": historical_status,
                    "mae": metric.get("mae"),
                    "rmse": metric.get("rmse"),
                    "bias": metric.get("bias"),
                    "interval_coverage_80": metric.get(
                        "interval_coverage_80"
                    ),
                    "directional_accuracy": metric.get(
                        "directional_accuracy"
                    ),
                    "drift_status": drift_row.get(
                        "drift_status",
                        "insufficient_sample",
                    ),
                }
            )

    return sorted(
        records,
        key=lambda row: (
            str(row["component"]),
            str(row["target_series"]),
            str(row["target_period"]),
        ),
    )


def build_evidence_flags(
    *,
    platform_snapshot: dict[str, Any],
    evaluation: dict[str, Any],
    current_forecasts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    readiness = platform_snapshot.get("readiness", {}) or {}

    if not bool(readiness.get("production_sources_ready", False)):
        flags.append(
            {
                "severity": "warning",
                "code": "production_sources_not_ready",
                "component": None,
                "target_series": None,
                "detail": (
                    "One or more governed production source states are not "
                    "ready at this as-of date."
                ),
            }
        )

    invalid_rows = int(
        evaluation.get("summary", {}).get("invalid_rows", 0) or 0
    )
    if invalid_rows:
        flags.append(
            {
                "severity": "warning",
                "code": "invalid_evaluation_rows",
                "component": None,
                "target_series": None,
                "detail": (
                    f"{invalid_rows} Phase 3B evaluation row(s) are invalid "
                    "and are excluded from performance evidence."
                ),
            }
        )

    due_releases = (
        platform_snapshot.get("freshness", {}).get("due_releases", []) or []
    )
    if due_releases:
        flags.append(
            {
                "severity": "warning",
                "code": "scheduled_source_releases_due",
                "component": None,
                "target_series": None,
                "detail": (
                    f"{len(due_releases)} scheduled source release(s) are "
                    "due relative to governed source state."
                ),
            }
        )

    for row in current_forecasts:
        status = str(row.get("historical_context_status") or "")
        if status == "no_resolved_history":
            flags.append(
                {
                    "severity": "info",
                    "code": "no_resolved_evaluation_history",
                    "component": row["component"],
                    "target_series": row["target_series"],
                    "detail": (
                        "No resolved first-release evaluation observation is "
                        "yet available for this target series."
                    ),
                }
            )
        elif status == "insufficient_for_interpretation":
            flags.append(
                {
                    "severity": "info",
                    "code": "insufficient_evaluation_history",
                    "component": row["component"],
                    "target_series": row["target_series"],
                    "detail": (
                        f"Only {row['n_resolved_history']} resolved "
                        "observation(s) are available; Phase 3C marks the "
                        "historical metrics insufficient for interpretation."
                    ),
                }
            )

    return sorted(
        flags,
        key=lambda row: (
            str(row["severity"]),
            str(row.get("component") or ""),
            str(row.get("target_series") or ""),
            str(row["code"]),
        ),
    )


def build_decision_intelligence_snapshot(
    repository: MacroRepository,
    *,
    as_of: date,
    project_root: Path,
    macro_snapshot_provider: MacroSnapshotProvider = build_macro_snapshot,
    ledger_provider: LedgerProvider = build_forecast_evaluation_ledger,
    revision_provider: RevisionProvider = build_revision_release_analytics,
) -> dict[str, Any]:
    if as_of > date.today():
        raise ValueError(
            "Decision-intelligence snapshot as-of date cannot be in the future."
        )

    platform_snapshot = macro_snapshot_provider(
        repository,
        as_of=as_of,
        project_root=project_root,
    )
    ledger = ledger_provider(
        repository,
        as_of=as_of,
        project_root=project_root,
    )
    evaluation = serialise_forecast_evaluation(
        ledger,
        as_of=as_of,
    )
    performance = serialise_performance_report(
        ledger,
        as_of=as_of,
    )
    revision_frames = revision_provider(
        repository,
        as_of=as_of,
        project_root=project_root,
    )
    revisions = serialise_revision_release_analytics(
        revision_frames,
        as_of=as_of,
    )

    current_forecasts = build_current_forecast_evidence(
        platform_snapshot=platform_snapshot,
        evaluation=evaluation,
        performance=performance,
        revisions=revisions,
    )
    flags = build_evidence_flags(
        platform_snapshot=platform_snapshot,
        evaluation=evaluation,
        current_forecasts=current_forecasts,
    )

    readiness = platform_snapshot.get("readiness", {}) or {}
    evaluation_summary = evaluation.get("summary", {}) or {}
    revision_summary = revisions.get("summary", {}) or {}

    semantic_payload = {
        "snapshot_schema_version": DECISION_INTELLIGENCE_SCHEMA_VERSION,
        "as_of": as_of.isoformat(),
        "contract": {
            "database_access": "read_only",
            "model_execution": "none",
            "data_download": "none",
            "governed_forecast_mutation": "none",
            "automatic_model_action": "none",
            "generative_ai_in_governed_core": False,
            "release_association_is_causal": False,
            "model1d_role": "research_only_separate",
            "semantic_hash_excludes_export_path_and_wall_clock": True,
        },
        "summary": {
            "production_sources_ready": bool(
                readiness.get("production_sources_ready", False)
            ),
            "platform_ready_for_downstream": bool(
                readiness.get("platform_ready_for_downstream", False)
            ),
            "current_target_count": len(current_forecasts),
            "evaluation_forecast_rows": int(
                evaluation_summary.get("forecast_rows", 0) or 0
            ),
            "resolved_evaluation_rows": int(
                evaluation_summary.get("resolved_rows", 0) or 0
            ),
            "unresolved_evaluation_rows": int(
                evaluation_summary.get("unresolved_rows", 0) or 0
            ),
            "invalid_evaluation_rows": int(
                evaluation_summary.get("invalid_rows", 0) or 0
            ),
            "comparable_revision_rows": int(
                revision_summary.get("comparable_revision_rows", 0) or 0
            ),
            "evidence_flag_count": len(flags),
        },
        "current_forecasts": current_forecasts,
        "evidence_flags": flags,
        "evaluation": evaluation,
        "performance": performance,
        "revisions": revisions,
        "freshness": platform_snapshot.get("freshness", {}),
        "calendar": platform_snapshot.get("calendar", {}),
        "provenance": {
            "platform_snapshot_hash": platform_snapshot.get("snapshot_hash"),
            "production": platform_snapshot.get("provenance", {}),
        },
        "model1d_research": {
            "separation": "research_only_no_production_evaluation_authority",
            "evidence": platform_snapshot.get("model1d", {}),
        },
    }

    return {
        **semantic_payload,
        "snapshot_hash": semantic_snapshot_hash(semantic_payload),
    }


def write_decision_intelligence_snapshot(
    snapshot: dict[str, Any],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            snapshot,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output_path
