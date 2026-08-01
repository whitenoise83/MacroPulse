from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.engine import prepare_state


def run_macro_state(
    repository: MacroRepository | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    state_as_of = as_of or date.today()
    prepared = prepare_state(repository, state_as_of)

    identity = prepared["identity"]
    run_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    source_runs = prepared["source_runs"]

    metrics = {
        "regime": prepared["regime"],
        "risk_flags": prepared["risk_flags"],
        "dimensions": {
            item.dimension: {
                "score": item.score,
                "lower_score": item.lower_score,
                "upper_score": item.upper_score,
                "label": item.label,
                "confidence": item.confidence,
                "details": item.details,
            }
            for item in prepared["dimensions"]
        },
        "source_cutoffs": {
            "oldest": str(prepared["oldest_source_cutoff"]),
            "newest": str(prepared["newest_source_cutoff"]),
            "spread_days": prepared["cutoff_spread_days"],
        },
        "source_versions": {
            "GDP": str(source_runs["GDP"]["model_version"]),
            "inflation": str(source_runs["inflation"]["model_version"]),
            "labour": str(source_runs["labour"]["model_version"]),
        },
        "prior_run_id": prepared["prior_run_id"],
    }

    run_record = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "run_timestamp": created_at,
                "state_as_of": prepared["as_of"],
                "status": "success",
                "primary_regime": prepared["regime"]["code"],
                "overall_confidence": prepared["overall_confidence"],
                "gdp_run_id": str(source_runs["GDP"]["run_id"]),
                "inflation_run_id": str(
                    source_runs["inflation"]["run_id"]
                ),
                "labour_run_id": str(source_runs["labour"]["run_id"]),
                "oldest_source_cutoff": prepared[
                    "oldest_source_cutoff"
                ],
                "newest_source_cutoff": prepared[
                    "newest_source_cutoff"
                ],
                "cutoff_spread_days": prepared["cutoff_spread_days"],
                "config_hash": identity.config_hash,
                "code_hash": identity.code_hash,
                "git_commit": identity.git_commit,
                "source_bundle_hash": prepared["source_bundle_hash"],
                "state_hash": prepared["state_hash"],
                "metrics_json": json.dumps(
                    metrics, sort_keys=True, default=str
                ),
                "notes": (
                    "Model 1D v0.1 transparent unified-state foundation; "
                    "not production approved."
                ),
            }
        ]
    )

    dimension_rows: list[dict[str, Any]] = []
    for item in prepared["dimensions"]:
        previous = prepared["prior_scores"].get(item.dimension)
        dimension_rows.append(
            {
                "run_id": run_id,
                "dimension": item.dimension,
                "score": item.score,
                "lower_score": item.lower_score,
                "upper_score": item.upper_score,
                "label": item.label,
                "confidence": item.confidence,
                "previous_run_id": prepared["prior_run_id"],
                "previous_score": previous,
                "delta_score": (
                    item.score - float(previous)
                    if previous is not None
                    else None
                ),
                "details_json": json.dumps(
                    item.details, sort_keys=True, default=str
                ),
                "created_at": created_at,
            }
        )
    dimensions = pd.DataFrame(dimension_rows)

    inputs = prepared["inputs"].copy()
    inputs.insert(0, "run_id", run_id)
    inputs["created_at"] = created_at
    inputs = inputs[
        [
            "run_id",
            "source_model_id",
            "source_model_version",
            "source_run_id",
            "source_target",
            "source_target_name",
            "target_period",
            "forecast_stage",
            "point_forecast",
            "lower_80",
            "upper_80",
            "information_cutoff",
            "data_as_of",
            "source_hash",
            "created_at",
        ]
    ]

    regime = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "regime_code": prepared["regime"]["code"],
                "regime_label": prepared["regime"]["label"],
                "is_primary": True,
                "rule_strength": prepared["regime"]["strength"],
                "rationale": prepared["regime"]["rationale"],
                "created_at": created_at,
            }
        ]
    )

    repository.save_macro_state_outputs(
        run_record, dimensions, inputs, regime
    )
    return {
        "run_id": run_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "lifecycle_status": identity.lifecycle_status,
        "state_as_of": prepared["as_of"],
        "primary_regime": prepared["regime"],
        "dimensions": dimensions,
        "inputs": inputs,
        "risk_flags": prepared["risk_flags"],
        "overall_confidence": prepared["overall_confidence"],
        "cutoff_spread_days": prepared["cutoff_spread_days"],
        "source_bundle_hash": prepared["source_bundle_hash"],
        "state_hash": prepared["state_hash"],
    }
