from __future__ import annotations

import math
import uuid
from datetime import date
from typing import Any, Mapping

import numpy as np
import pandas as pd

from macropulse.macro_state.prospective_shadow import (
    REQUIRED_BENCHMARKS,
    ProspectiveShadowPlan,
    canonical_json,
    probability_diagnostics,
    sha256_json,
    validate_probability_vector,
)


def _normalise_timestamp(value: object, field_name: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except Exception as exc:
        raise ValueError(f"{field_name} is not a valid timestamp: {value!r}") from exc
    if pd.isna(timestamp):
        raise ValueError(f"{field_name} must not be null")
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp


def validate_actual_target(
    *,
    actual_family: str,
    actual_probabilities: Mapping[str, float],
    actual_confidence: float,
    plan: ProspectiveShadowPlan,
) -> dict[str, float]:
    vector = validate_probability_vector(actual_probabilities, plan)
    diagnostics = probability_diagnostics(vector, plan)
    family = str(actual_family)
    if family not in plan.family_order:
        raise ValueError(f"Actual family is outside the frozen contract: {family}")
    if diagnostics["top1_family"] != family:
        raise ValueError(
            "actual_family must equal the deterministic top family of the "
            "actual probability vector"
        )
    confidence = float(actual_confidence)
    if not math.isfinite(confidence) or confidence < 0.0 or confidence > 1.0:
        raise ValueError("actual_confidence must be finite and between 0 and 1")
    if abs(confidence - float(vector[family])) > plan.probability_tolerance:
        raise ValueError(
            "actual_confidence must equal the probability assigned to "
            "actual_family"
        )
    return vector


def transition_flag(
    actual_family: str,
    previous_actual_family: str | None,
) -> bool:
    if previous_actual_family is None or pd.isna(previous_actual_family):
        return False
    return str(actual_family) != str(previous_actual_family)


def target_hash(
    *,
    state_date: date,
    target_mode: str,
    target_horizon_days: int,
    target_available_date: date,
    target_components: pd.DataFrame,
    actual_dimensions: Mapping[str, float],
    actual_family: str,
    actual_probabilities: Mapping[str, float],
    actual_confidence: float,
    plan: ProspectiveShadowPlan,
) -> str:
    vector = validate_actual_target(
        actual_family=actual_family,
        actual_probabilities=actual_probabilities,
        actual_confidence=actual_confidence,
        plan=plan,
    )
    required_components = {
        "source_target",
        "target_period",
        "requested_evaluation_date",
        "snapshot_date",
        "snapshot_gap_days",
        "actual_value",
    }
    missing = sorted(required_components - set(target_components.columns))
    if missing:
        raise ValueError(f"Target components are missing columns: {missing}")
    components = []
    ordered = target_components.sort_values(
        ["source_target", "target_period"]
    )
    for row in ordered.itertuples(index=False):
        components.append(
            {
                "source_target": str(row.source_target),
                "target_period": str(row.target_period),
                "requested_evaluation_date": str(
                    pd.Timestamp(row.requested_evaluation_date).date()
                ),
                "snapshot_date": str(pd.Timestamp(row.snapshot_date).date()),
                "snapshot_gap_days": int(row.snapshot_gap_days),
                "actual_value": float(row.actual_value),
            }
        )
    dimensions = {
        name: float(actual_dimensions[name])
        for name in ("growth", "inflation", "labour")
    }
    return sha256_json(
        {
            "state_date": str(state_date),
            "target_mode": str(target_mode),
            "target_horizon_days": int(target_horizon_days),
            "target_available_date": str(target_available_date),
            "components": components,
            "actual_dimensions": dimensions,
            "actual_family": str(actual_family),
            "actual_probabilities": vector,
            "actual_confidence": float(actual_confidence),
        }
    )


def score_prediction(
    *,
    prediction: Mapping[str, Any],
    actual_family: str,
    actual_probabilities: Mapping[str, float],
    target_hash_value: str,
    log_loss_floor: float,
    plan: ProspectiveShadowPlan,
) -> dict[str, Any]:
    if not 0.0 < float(log_loss_floor) < 1.0:
        raise ValueError("log_loss_floor must be strictly between zero and one")
    predicted = validate_probability_vector(
        _json_probability_map(prediction["predicted_probabilities_json"]),
        plan,
    )
    actual = validate_probability_vector(actual_probabilities, plan)
    expected = probability_diagnostics(predicted, plan)
    for field in (
        "predicted_family",
        "top1_family",
        "top2_family",
        "top3_family",
        "probability_vector_hash",
    ):
        if str(prediction[field]) != str(expected[field]):
            raise ValueError(
                f"Persisted prediction field {field} does not reconcile "
                "with the governed probability vector"
            )
    for field in (
        "top1_probability",
        "top2_probability",
        "top3_probability",
        "top1_top2_gap",
        "entropy",
        "probability_sum",
    ):
        if abs(float(prediction[field]) - float(expected[field])) > 1.0e-9:
            raise ValueError(
                f"Persisted prediction field {field} does not reconcile "
                "with the governed probability vector"
            )

    p = np.asarray([predicted[family] for family in plan.family_order], dtype=float)
    a = np.asarray([actual[family] for family in plan.family_order], dtype=float)
    brier = float(np.square(p - a).sum())
    log_loss = float(-np.sum(a * np.log(np.maximum(p, log_loss_floor))))
    actual_probability = float(predicted[str(actual_family)])
    top1_hit = str(actual_family) == str(expected["top1_family"])
    top2_hit = str(actual_family) in {
        str(expected["top1_family"]),
        str(expected["top2_family"]),
    }
    top3_hit = str(actual_family) in {
        str(expected["top1_family"]),
        str(expected["top2_family"]),
        str(expected["top3_family"]),
    }
    evaluation_payload = {
        "benchmark_id": str(prediction["benchmark_id"]),
        "prediction_vector_hash": str(prediction["probability_vector_hash"]),
        "target_hash": str(target_hash_value),
        "actual_family": str(actual_family),
        "actual_probability": actual_probability,
        "brier_score": brier,
        "log_loss": log_loss,
        "top1_hit": bool(top1_hit),
        "top2_hit": bool(top2_hit),
        "top3_hit": bool(top3_hit),
    }
    return {
        **evaluation_payload,
        "evaluation_hash": sha256_json(evaluation_payload),
    }


def _json_probability_map(value: Any) -> dict[str, float]:
    if isinstance(value, Mapping):
        raw = value
    else:
        try:
            import json

            raw = json.loads(str(value))
        except Exception as exc:
            raise ValueError("Probability JSON is invalid") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("Probability JSON must decode to an object")
    try:
        return {str(key): float(item) for key, item in raw.items()}
    except (TypeError, ValueError) as exc:
        raise ValueError("Probability JSON values must be numeric") from exc


def build_outcome_rows(
    *,
    shadow_run: Mapping[str, Any],
    predictions: pd.DataFrame,
    resolved_at: pd.Timestamp,
    target_available_date: date,
    target_vintage_id: str,
    actual_family: str,
    actual_probabilities: Mapping[str, float],
    actual_confidence: float,
    previous_actual_family: str | None,
    target_hash_value: str,
    log_loss_floor: float,
    plan: ProspectiveShadowPlan,
) -> pd.DataFrame:
    if len(predictions) != 2:
        raise ValueError("Exactly two persisted predictions are required")
    observed = set(predictions["benchmark_id"].astype(str))
    if observed != set(REQUIRED_BENCHMARKS):
        raise ValueError(
            "Persisted predictions must contain source and rolling_frequency"
        )
    if predictions["benchmark_id"].duplicated().any():
        raise ValueError("Persisted prediction benchmark IDs must be unique")

    resolved_timestamp = _normalise_timestamp(resolved_at, "resolved_at")
    target_date = pd.Timestamp(target_available_date).date()
    if resolved_timestamp < pd.Timestamp(target_date):
        raise ValueError("Outcome resolution cannot precede target availability")
    vector = validate_actual_target(
        actual_family=actual_family,
        actual_probabilities=actual_probabilities,
        actual_confidence=actual_confidence,
        plan=plan,
    )
    previous = (
        None
        if previous_actual_family is None or pd.isna(previous_actual_family)
        else str(previous_actual_family)
    )
    transitioned = transition_flag(actual_family, previous)
    created_at = resolved_timestamp
    rows: list[dict[str, Any]] = []
    for prediction in predictions.sort_values("benchmark_id").to_dict("records"):
        score = score_prediction(
            prediction=prediction,
            actual_family=str(actual_family),
            actual_probabilities=vector,
            target_hash_value=target_hash_value,
            log_loss_floor=log_loss_floor,
            plan=plan,
        )
        rows.append(
            {
                "outcome_id": str(uuid.uuid4()),
                "shadow_run_id": str(shadow_run["shadow_run_id"]),
                "model_version": str(shadow_run["model_version"]),
                "state_date": pd.Timestamp(shadow_run["state_date"]).date(),
                "benchmark_id": str(prediction["benchmark_id"]),
                "resolved_at": resolved_timestamp,
                "target_mode": str(shadow_run["target_mode"]),
                "target_horizon_days": int(
                    shadow_run["target_horizon_days"]
                ),
                "target_available_date": target_date,
                "target_vintage_id": str(target_vintage_id),
                "actual_family": str(actual_family),
                "actual_probabilities_json": canonical_json(vector),
                "actual_confidence": float(actual_confidence),
                "actual_probability": float(score["actual_probability"]),
                "brier_score": float(score["brier_score"]),
                "log_loss": float(score["log_loss"]),
                "top1_hit": bool(score["top1_hit"]),
                "top2_hit": bool(score["top2_hit"]),
                "top3_hit": bool(score["top3_hit"]),
                "previous_actual_family": previous,
                "transition_flag": bool(transitioned),
                "target_hash": str(target_hash_value),
                "evaluation_hash": str(score["evaluation_hash"]),
                "no_look_ahead_pass": True,
                "created_at": created_at,
            }
        )
    return pd.DataFrame(rows)
