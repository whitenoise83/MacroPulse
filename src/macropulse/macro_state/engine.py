from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.versioning import (
    current_macro_state_identity,
    load_macro_state_governance,
)


GDP_TARGET = "GDPC1"
INFLATION_TARGETS = ("PCEPILFE", "CPILFESL", "PCEPI", "CPIAUCSL")
LABOUR_TARGETS = ("PAYEMS", "UNRATE", "CES0500000003")


@dataclass(frozen=True)
class DimensionResult:
    dimension: str
    score: float
    lower_score: float
    upper_score: float
    label: str
    confidence: float
    details: dict[str, Any]


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        _canonical_json(value).encode("utf-8")
    ).hexdigest()


def piecewise_score(
    value: float,
    anchors: Iterable[Iterable[float]],
) -> float:
    points = sorted(
        [(float(x), float(score)) for x, score in anchors],
        key=lambda item: item[0],
    )
    if len(points) < 2:
        raise ValueError("At least two score anchors are required.")
    x = float(value)
    if x <= points[0][0]:
        return float(points[0][1])
    if x >= points[-1][0]:
        return float(points[-1][1])
    for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
        if x0 <= x <= x1:
            weight = (x - x0) / (x1 - x0)
            return float(y0 + weight * (y1 - y0))
    raise RuntimeError("Unable to interpolate macro-state score.")


def score_label(
    dimension: str,
    score: float,
    config: dict[str, Any],
) -> str:
    for upper, label in config["labels"][dimension]:
        if float(score) < float(upper):
            return str(label)
    return str(config["labels"][dimension][-1][1])


def _weighted_average(
    values: dict[str, float],
    weights: dict[str, float],
) -> float:
    missing = sorted(set(weights).difference(values))
    if missing:
        raise ValueError(f"Missing weighted inputs: {missing}")
    total = float(sum(float(weights[key]) for key in weights))
    if total <= 0:
        raise ValueError("Input weights must sum to a positive value.")
    return float(
        sum(float(values[key]) * float(weights[key]) for key in weights)
        / total
    )


def _confidence_from_score_interval(
    lower_score: float,
    upper_score: float,
    minimum: float,
) -> float:
    width = max(0.0, float(upper_score) - float(lower_score))
    confidence = 95.0 - 22.5 * width
    return float(np.clip(confidence, minimum, 95.0))


def _latest_registry_status(
    repository: MacroRepository,
    model_id: str,
    model_version: str,
) -> str | None:
    frame = repository.query_df(
        """
        SELECT lifecycle_status
        FROM model_registry
        WHERE model_id = ? AND model_version = ?
        ORDER BY registered_at DESC
        LIMIT 1
        """,
        [model_id, model_version],
    )
    if frame.empty:
        return None
    return str(frame.iloc[0]["lifecycle_status"])


def _require_source_registry(
    repository: MacroRepository,
    config: dict[str, Any],
) -> None:
    if not bool(
        config.get("governance", {}).get(
            "require_production_source_registry", True
        )
    ):
        return
    failures: list[str] = []
    for name, values in config["required_sources"].items():
        observed = _latest_registry_status(
            repository,
            str(values["model_id"]),
            str(values["model_version"]),
        )
        expected = str(values.get("lifecycle_status", "production"))
        if observed != expected:
            failures.append(
                f"{name}: registry lifecycle={observed!r}, expected={expected!r}"
            )
    if failures:
        raise RuntimeError(
            "Model 1D requires registered production source identities. "
            + "; ".join(failures)
        )


def _select_gdp(
    repository: MacroRepository,
    as_of: date,
    source: dict[str, Any],
) -> tuple[pd.Series, pd.DataFrame]:
    run = repository.query_df(
        """
        SELECT *
        FROM forecast_registry
        WHERE model_id = ?
          AND model_version = ?
          AND status = 'success'
          AND information_cutoff <= ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [source["model_id"], source["model_version"], as_of],
    )
    if run.empty:
        raise RuntimeError(
            "No successful Model 1A v1.0.0 production forecast exists "
            f"with information cutoff on or before {as_of}."
        )
    row = run.iloc[0]
    inputs = pd.DataFrame(
        [
            {
                "source_model_id": str(row["model_id"]),
                "source_model_version": str(row["model_version"]),
                "source_run_id": str(row["run_id"]),
                "source_target": GDP_TARGET,
                "source_target_name": "Real GDP growth",
                "target_period": str(row["target_period"]),
                "forecast_stage": str(row["forecast_stage"] or ""),
                "point_forecast": float(row["production_forecast"]),
                "lower_80": float(row["lower_80"]),
                "upper_80": float(row["upper_80"]),
                "information_cutoff": pd.Timestamp(
                    row["information_cutoff"]
                ).date(),
                "data_as_of": (
                    pd.Timestamp(row["data_as_of"]).date()
                    if pd.notna(row["data_as_of"])
                    else None
                ),
                "source_created_at": pd.Timestamp(row["created_at"]),
            }
        ]
    )
    return row, inputs


def _select_live_family(
    repository: MacroRepository,
    as_of: date,
    source: dict[str, Any],
    run_table: str,
    forecast_table: str,
    required_targets: tuple[str, ...],
) -> tuple[pd.Series, pd.DataFrame]:
    run = repository.query_df(
        f"""
        SELECT *
        FROM {run_table}
        WHERE model_id = ?
          AND model_version = ?
          AND status = 'success'
          AND information_cutoff <= ?
        ORDER BY run_timestamp DESC
        LIMIT 1
        """,
        [source["model_id"], source["model_version"], as_of],
    )
    if run.empty:
        raise RuntimeError(
            f"No successful {source['model_id']} v{source['model_version']} "
            f"production run exists with information cutoff on or before {as_of}."
        )
    row = run.iloc[0]
    forecasts = repository.query_df(
        f"""
        SELECT *
        FROM {forecast_table}
        WHERE run_id = ?
        ORDER BY target_series
        """,
        [row["run_id"]],
    )
    observed = set(forecasts["target_series"].astype(str))
    missing = sorted(set(required_targets).difference(observed))
    if missing:
        raise RuntimeError(
            f"Source run {row['run_id']} is missing targets: {missing}"
        )
    forecasts = forecasts.loc[
        forecasts["target_series"].astype(str).isin(required_targets)
    ].copy()
    inputs = pd.DataFrame(
        {
            "source_model_id": str(row["model_id"]),
            "source_model_version": str(row["model_version"]),
            "source_run_id": str(row["run_id"]),
            "source_target": forecasts["target_series"].astype(str),
            "source_target_name": forecasts["target_name"].astype(str),
            "target_period": forecasts["target_period"].astype(str),
            "forecast_stage": forecasts["forecast_stage"].astype(str),
            "point_forecast": pd.to_numeric(
                forecasts["stable_point_forecast"], errors="raise"
            ),
            "lower_80": pd.to_numeric(
                forecasts["lower_80"], errors="raise"
            ),
            "upper_80": pd.to_numeric(
                forecasts["upper_80"], errors="raise"
            ),
            "information_cutoff": pd.Timestamp(
                row["information_cutoff"]
            ).date(),
            "data_as_of": (
                pd.Timestamp(row["data_as_of"]).date()
                if pd.notna(row["data_as_of"])
                else None
            ),
            "source_created_at": pd.Timestamp(row["run_timestamp"]),
        }
    )
    return row, inputs.reset_index(drop=True)


def select_source_bundle(
    repository: MacroRepository,
    as_of: date,
    config: dict[str, Any],
) -> tuple[dict[str, pd.Series], pd.DataFrame]:
    _require_source_registry(repository, config)
    gdp_run, gdp_inputs = _select_gdp(
        repository, as_of, config["required_sources"]["GDP"]
    )
    inflation_run, inflation_inputs = _select_live_family(
        repository,
        as_of,
        config["required_sources"]["inflation"],
        "inflation_live_runs",
        "inflation_live_forecasts",
        INFLATION_TARGETS,
    )
    labour_run, labour_inputs = _select_live_family(
        repository,
        as_of,
        config["required_sources"]["labour"],
        "labour_live_runs",
        "labour_live_forecasts",
        LABOUR_TARGETS,
    )
    inputs = pd.concat(
        [gdp_inputs, inflation_inputs, labour_inputs],
        ignore_index=True,
    )
    source_hashes: list[str] = []
    for row in inputs.itertuples(index=False):
        payload = {
            "source_model_id": row.source_model_id,
            "source_model_version": row.source_model_version,
            "source_run_id": row.source_run_id,
            "source_target": row.source_target,
            "target_period": row.target_period,
            "forecast_stage": row.forecast_stage,
            "point_forecast": row.point_forecast,
            "lower_80": row.lower_80,
            "upper_80": row.upper_80,
            "information_cutoff": row.information_cutoff,
            "data_as_of": row.data_as_of,
        }
        source_hashes.append(_sha256(payload))
    inputs["source_hash"] = source_hashes
    return {
        "GDP": gdp_run,
        "inflation": inflation_run,
        "labour": labour_run,
    }, inputs


def _row_map(inputs: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        str(row["source_target"]): row
        for _, row in inputs.iterrows()
    }


def build_dimensions(
    inputs: pd.DataFrame,
    config: dict[str, Any],
) -> list[DimensionResult]:
    rows = _row_map(inputs)
    minimum = float(
        config["governance"].get("minimum_dimension_confidence", 30)
    )

    gdp = rows[GDP_TARGET]
    growth_score = piecewise_score(
        float(gdp["point_forecast"]),
        config["score_anchors"]["growth"],
    )
    growth_bounds = sorted(
        [
            piecewise_score(
                float(gdp["lower_80"]),
                config["score_anchors"]["growth"],
            ),
            piecewise_score(
                float(gdp["upper_80"]),
                config["score_anchors"]["growth"],
            ),
        ]
    )
    growth = DimensionResult(
        dimension="growth",
        score=growth_score,
        lower_score=growth_bounds[0],
        upper_score=growth_bounds[1],
        label=score_label("growth", growth_score, config),
        confidence=_confidence_from_score_interval(
            growth_bounds[0], growth_bounds[1], minimum
        ),
        details={
            "source_target": GDP_TARGET,
            "point_forecast": float(gdp["point_forecast"]),
            "lower_80": float(gdp["lower_80"]),
            "upper_80": float(gdp["upper_80"]),
            "unit": "annualised quarter-on-quarter percent",
        },
    )

    inflation_weights = {
        str(key): float(value)
        for key, value in config["inputs"]["inflation_weights"].items()
    }
    inflation_scores: dict[str, float] = {}
    inflation_lowers: dict[str, float] = {}
    inflation_uppers: dict[str, float] = {}
    inflation_details: dict[str, Any] = {}
    for target in INFLATION_TARGETS:
        row = rows[target]
        anchors = config["score_anchors"]["inflation"][target]
        point = piecewise_score(float(row["point_forecast"]), anchors)
        interval_scores = sorted(
            [
                piecewise_score(float(row["lower_80"]), anchors),
                piecewise_score(float(row["upper_80"]), anchors),
            ]
        )
        inflation_scores[target] = point
        inflation_lowers[target] = interval_scores[0]
        inflation_uppers[target] = interval_scores[1]
        inflation_details[target] = {
            "weight": inflation_weights[target],
            "point_forecast": float(row["point_forecast"]),
            "lower_80": float(row["lower_80"]),
            "upper_80": float(row["upper_80"]),
            "score": point,
        }
    inflation_score = _weighted_average(
        inflation_scores, inflation_weights
    )
    inflation_lower = _weighted_average(
        inflation_lowers, inflation_weights
    )
    inflation_upper = _weighted_average(
        inflation_uppers, inflation_weights
    )
    inflation = DimensionResult(
        dimension="inflation",
        score=inflation_score,
        lower_score=inflation_lower,
        upper_score=inflation_upper,
        label=score_label("inflation", inflation_score, config),
        confidence=_confidence_from_score_interval(
            inflation_lower, inflation_upper, minimum
        ),
        details={
            "weighted_targets": inflation_details,
            "unit": "normalized pressure score",
        },
    )

    labour_weights = {
        str(key): float(value)
        for key, value in config["inputs"]["labour_weights"].items()
    }
    labour_scores: dict[str, float] = {}
    labour_lowers: dict[str, float] = {}
    labour_uppers: dict[str, float] = {}
    labour_details: dict[str, Any] = {}
    for target in LABOUR_TARGETS:
        row = rows[target]
        anchors = config["score_anchors"]["labour"][target]
        point = piecewise_score(float(row["point_forecast"]), anchors)
        interval_scores = sorted(
            [
                piecewise_score(float(row["lower_80"]), anchors),
                piecewise_score(float(row["upper_80"]), anchors),
            ]
        )
        labour_scores[target] = point
        labour_lowers[target] = interval_scores[0]
        labour_uppers[target] = interval_scores[1]
        labour_details[target] = {
            "weight": labour_weights[target],
            "point_forecast": float(row["point_forecast"]),
            "lower_80": float(row["lower_80"]),
            "upper_80": float(row["upper_80"]),
            "score": point,
        }
    labour_score = _weighted_average(labour_scores, labour_weights)
    labour_lower = _weighted_average(labour_lowers, labour_weights)
    labour_upper = _weighted_average(labour_uppers, labour_weights)
    labour = DimensionResult(
        dimension="labour",
        score=labour_score,
        lower_score=labour_lower,
        upper_score=labour_upper,
        label=score_label("labour", labour_score, config),
        confidence=_confidence_from_score_interval(
            labour_lower, labour_upper, minimum
        ),
        details={
            "weighted_targets": labour_details,
            "unit": "normalized labour-tightness score",
        },
    )
    return [growth, inflation, labour]


def classify_regime(
    growth: float,
    inflation: float,
    labour: float,
) -> tuple[str, str, float, str]:
    g = float(growth)
    i = float(inflation)
    l = float(labour)

    if g <= -0.75 and l <= -0.75:
        return (
            "hard_landing_risk",
            "Hard-landing risk",
            min(1.0, (abs(g) + abs(l)) / 3.0),
            "Growth is materially weak and labour conditions are slackening.",
        )
    if g <= -0.75 and i >= 0.75:
        return (
            "stagflation_risk",
            "Stagflation risk",
            min(1.0, (abs(g) + abs(i)) / 3.0),
            "Growth is weak while inflation pressure remains elevated.",
        )
    if g >= 0.75 and i >= 0.75 and l >= 0.50:
        return (
            "overheating",
            "Overheating",
            min(1.0, (g + i + l) / 4.5),
            "Growth, inflation pressure, and labour tightness are all elevated.",
        )
    if g >= 0.25 and i <= -0.25 and l >= -0.50:
        return (
            "disinflationary_expansion",
            "Disinflationary expansion",
            min(1.0, (g + abs(i) + max(l, 0.0)) / 3.5),
            "Growth remains positive while inflation pressure is easing.",
        )
    if -0.25 <= g <= 0.75 and -0.40 <= i <= 0.40 and -0.50 <= l <= 0.75:
        return (
            "balanced_expansion",
            "Balanced expansion",
            max(0.50, 1.0 - (abs(g) + abs(i) + abs(l)) / 4.0),
            "Growth is near trend, inflation pressure is near target-consistent, "
            "and labour conditions are broadly balanced.",
        )
    if g >= 0.25 and i >= 0.25:
        return (
            "reflation",
            "Reflation",
            min(1.0, (g + i + max(l, 0.0)) / 4.0),
            "Growth and inflation pressure are rising together.",
        )
    if g <= -0.25 and i <= 0.25:
        return (
            "demand_slowdown",
            "Demand slowdown",
            min(1.0, (abs(g) + max(-l, 0.0) + max(-i, 0.0)) / 3.5),
            "Growth is below trend without a dominant inflation-pressure signal.",
        )
    return (
        "mixed_transition",
        "Mixed transition",
        0.50,
        "The three dimensions do not form a dominant canonical macro regime.",
    )


def risk_flags(
    inputs: pd.DataFrame,
    cutoff_spread_days: int,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = _row_map(inputs)
    thresholds = config["governance"]["risk_thresholds"]
    flags: list[dict[str, Any]] = []

    if float(rows[GDP_TARGET]["lower_80"]) < float(
        thresholds["gdp_lower_80"]
    ):
        flags.append(
            {
                "code": "growth_downside_interval",
                "severity": "medium",
                "message": "The GDP 80% interval includes contraction.",
            }
        )
    if float(rows["PCEPILFE"]["upper_80"]) > float(
        thresholds["core_pce_upper_80"]
    ):
        flags.append(
            {
                "code": "core_pce_upside_interval",
                "severity": "medium",
                "message": "The core PCE 80% interval includes renewed high inflation.",
            }
        )
    if float(rows["PAYEMS"]["lower_80"]) < float(
        thresholds["payroll_lower_80"]
    ):
        flags.append(
            {
                "code": "payroll_downside_interval",
                "severity": "medium",
                "message": "The payroll 80% interval includes job losses.",
            }
        )
    if float(rows["UNRATE"]["upper_80"]) > float(
        thresholds["unemployment_upper_80"]
    ):
        flags.append(
            {
                "code": "unemployment_upside_interval",
                "severity": "medium",
                "message": "The unemployment-rate 80% interval exceeds the configured risk threshold.",
            }
        )
    preferred = int(
        config["governance"]["maximum_preferred_cutoff_spread_days"]
    )
    if int(cutoff_spread_days) > preferred:
        flags.append(
            {
                "code": "asynchronous_source_cutoffs",
                "severity": "low",
                "message": (
                    "Production source cutoffs are more dispersed than the "
                    f"preferred {preferred}-day limit."
                ),
            }
        )
    return flags


def latest_prior_state(
    repository: MacroRepository,
) -> tuple[str | None, dict[str, float]]:
    run = repository.query_df(
        """
        SELECT run_id
        FROM macro_state_runs
        WHERE status = 'success'
        ORDER BY run_timestamp DESC
        LIMIT 1
        """
    )
    if run.empty:
        return None, {}
    run_id = str(run.iloc[0]["run_id"])
    dimensions = repository.query_df(
        """
        SELECT dimension, score
        FROM macro_state_dimensions
        WHERE run_id = ?
        """,
        [run_id],
    )
    return run_id, {
        str(row.dimension): float(row.score)
        for row in dimensions.itertuples(index=False)
    }


def prepare_state(
    repository: MacroRepository,
    as_of: date,
) -> dict[str, Any]:
    config = load_macro_state_governance()
    identity = current_macro_state_identity()
    source_runs, inputs = select_source_bundle(
        repository, as_of, config
    )

    cutoffs = pd.to_datetime(inputs["information_cutoff"]).dt.date
    oldest = min(cutoffs)
    newest = max(cutoffs)
    spread = int((newest - oldest).days)
    maximum = int(
        config["governance"]["maximum_allowed_cutoff_spread_days"]
    )
    if spread > maximum:
        raise RuntimeError(
            f"Source cutoff spread is {spread} days; maximum allowed is "
            f"{maximum} days."
        )

    dimensions = build_dimensions(inputs, config)
    dimension_map = {item.dimension: item for item in dimensions}
    regime = classify_regime(
        dimension_map["growth"].score,
        dimension_map["inflation"].score,
        dimension_map["labour"].score,
    )
    flags = risk_flags(inputs, spread, config)

    prior_run_id, prior_scores = latest_prior_state(repository)
    overall_confidence = float(
        np.mean([item.confidence for item in dimensions])
    )
    preferred = int(
        config["governance"]["maximum_preferred_cutoff_spread_days"]
    )
    if spread > preferred:
        overall_confidence = max(25.0, overall_confidence - 15.0)

    source_payload = [
        {
            key: (
                value.isoformat()
                if hasattr(value, "isoformat")
                else value
            )
            for key, value in row.items()
            if key not in {"source_created_at"}
        }
        for row in inputs.to_dict(orient="records")
    ]
    source_bundle_hash = _sha256(source_payload)

    dimension_payload = [
        {
            "dimension": item.dimension,
            "score": item.score,
            "lower_score": item.lower_score,
            "upper_score": item.upper_score,
            "label": item.label,
            "confidence": item.confidence,
        }
        for item in dimensions
    ]
    state_hash = _sha256(
        {
            "identity": identity.as_dict(),
            "as_of": as_of,
            "source_bundle_hash": source_bundle_hash,
            "dimensions": dimension_payload,
            "regime": regime,
            "flags": flags,
        }
    )
    return {
        "identity": identity,
        "as_of": as_of,
        "source_runs": source_runs,
        "inputs": inputs,
        "dimensions": dimensions,
        "regime": {
            "code": regime[0],
            "label": regime[1],
            "strength": regime[2],
            "rationale": regime[3],
        },
        "risk_flags": flags,
        "prior_run_id": prior_run_id,
        "prior_scores": prior_scores,
        "oldest_source_cutoff": oldest,
        "newest_source_cutoff": newest,
        "cutoff_spread_days": spread,
        "overall_confidence": overall_confidence,
        "source_bundle_hash": source_bundle_hash,
        "state_hash": state_hash,
    }
