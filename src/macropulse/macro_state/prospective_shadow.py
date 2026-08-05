from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd


SOURCE_BENCHMARK = "source"
ROLLING_BENCHMARK = "rolling_frequency"
REQUIRED_BENCHMARKS = (SOURCE_BENCHMARK, ROLLING_BENCHMARK)
REQUIRED_DIMENSIONS = ("growth", "inflation", "labour")

REGIME_TO_FAMILY = {
    "hard_landing_risk": "contraction",
    "stagflation_risk": "adverse_supply",
    "overheating": "inflationary_expansion",
    "disinflationary_expansion": "benign_expansion",
    "balanced_expansion": "benign_expansion",
    "reflation": "inflationary_expansion",
    "demand_slowdown": "contraction",
    "mixed_transition": "mixed",
}


@dataclass(frozen=True)
class ProspectiveShadowPlan:
    model_version: str
    source_version: str
    source_candidate_id: str
    source_evidence_stem: str
    source_stability_id: str
    source_core_candidate_id: str
    primary_comparator: str
    target_mode: str
    target_horizon_days: int
    family_order: tuple[str, ...]
    probability_sum: float
    probability_tolerance: float
    rolling_window_months: int
    uncertainty_draws: int
    random_seed: int
    normal_interval_z: float
    robust_mad_constant: float
    robust_minimum_history: int
    robust_clip: float


def prospective_shadow_plan(config: Mapping[str, Any]) -> ProspectiveShadowPlan:
    section = config["prospective_transition_shadow"]
    evidence = section["source_evidence"]
    engine = section["engine"]
    probability = section["probability_contract"]
    source = section["frozen_source"]
    comparator = section["comparator"]
    target = section["target"]

    family_order = tuple(str(item) for item in probability["family_order"])
    if len(family_order) != 5 or len(set(family_order)) != 5:
        raise ValueError("The prospective shadow requires five unique families.")
    if str(comparator["benchmark_id"]) != ROLLING_BENCHMARK:
        raise ValueError("rolling_frequency must remain the primary comparator.")
    if str(target["mode"]) != "fixed_horizon_90d":
        raise ValueError("The target mode must remain fixed_horizon_90d.")
    if str(source["model_version"]) != "0.3.6":
        raise ValueError("The frozen source version must remain 0.3.6.")

    return ProspectiveShadowPlan(
        model_version=str(section["model_version"]),
        source_version=str(source["model_version"]),
        source_candidate_id=str(source["candidate_id"]),
        source_evidence_stem=str(evidence["stem"]),
        source_stability_id=str(evidence["stability_id"]),
        source_core_candidate_id=str(evidence["core_candidate_id"]),
        primary_comparator=str(comparator["benchmark_id"]),
        target_mode=str(target["mode"]),
        target_horizon_days=int(target["horizon_days"]),
        family_order=family_order,
        probability_sum=float(probability["required_sum"]),
        probability_tolerance=float(probability["sum_tolerance"]),
        rolling_window_months=int(engine["rolling_window_months"]),
        uncertainty_draws=int(engine["uncertainty_draws"]),
        random_seed=int(engine["random_seed"]),
        normal_interval_z=float(engine["normal_interval_z"]),
        robust_mad_constant=float(engine["robust_mad_constant"]),
        robust_minimum_history=int(engine["robust_minimum_history"]),
        robust_clip=float(engine["robust_clip"]),
    )


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def month_end(value: date | pd.Timestamp | str) -> date:
    return pd.Timestamp(value).to_period("M").end_time.date()


def validate_probability_vector(
    probabilities: Mapping[str, float],
    plan: ProspectiveShadowPlan,
) -> dict[str, float]:
    observed = set(str(key) for key in probabilities)
    expected = set(plan.family_order)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ValueError(
            "Probability families do not match the frozen contract; "
            f"missing={missing}, extra={extra}"
        )

    vector: dict[str, float] = {}
    for family in plan.family_order:
        value = float(probabilities[family])
        if not math.isfinite(value):
            raise ValueError(f"Probability for {family} must be finite.")
        if value < 0.0:
            raise ValueError(f"Probability for {family} cannot be negative.")
        vector[family] = value

    total = float(sum(vector.values()))
    if abs(total - plan.probability_sum) > plan.probability_tolerance:
        raise ValueError(
            "Probability vector must sum to "
            f"{plan.probability_sum} within {plan.probability_tolerance}; "
            f"observed {total}"
        )
    return vector


def normalise_probability_vector(
    probabilities: Mapping[str, float],
    plan: ProspectiveShadowPlan,
) -> dict[str, float]:
    raw = {family: max(0.0, float(probabilities.get(family, 0.0))) for family in plan.family_order}
    total = float(sum(raw.values()))
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("Probability vector has no positive finite mass.")
    normalised = {family: raw[family] / total for family in plan.family_order}
    residual = plan.probability_sum - float(sum(normalised.values()))
    normalised[plan.family_order[-1]] += residual
    return validate_probability_vector(normalised, plan)


def probability_diagnostics(
    probabilities: Mapping[str, float],
    plan: ProspectiveShadowPlan,
) -> dict[str, Any]:
    vector = validate_probability_vector(probabilities, plan)
    order_index = {family: index for index, family in enumerate(plan.family_order)}
    ordered = sorted(
        vector.items(),
        key=lambda item: (-item[1], order_index[item[0]]),
    )
    array = np.asarray([vector[family] for family in plan.family_order], dtype=float)
    positive = array[array > 0.0]
    entropy = float(-(positive * np.log(positive)).sum())
    return {
        "predicted_family": ordered[0][0],
        "top1_family": ordered[0][0],
        "top2_family": ordered[1][0],
        "top3_family": ordered[2][0],
        "top1_probability": float(ordered[0][1]),
        "top2_probability": float(ordered[1][1]),
        "top3_probability": float(ordered[2][1]),
        "top1_top2_gap": float(ordered[0][1] - ordered[1][1]),
        "entropy": entropy,
        "probability_sum": float(array.sum()),
        "probability_vector_hash": sha256_json(vector),
        "predicted_probabilities_json": canonical_json(vector),
    }


def _orientation(config: Mapping[str, Any], target: str) -> float:
    target_centered = config["tournament"]["normalization_candidates"]["target_centered"]
    return float(target_centered["orientation"].get(target, 1.0))


def _fallback_transform(
    value: float,
    target: str,
    config: Mapping[str, Any],
) -> float:
    target_centered = config["tournament"]["normalization_candidates"]["target_centered"]
    center = float(target_centered["centers"][target])
    scale = float(target_centered["scales"][target])
    if scale <= 0.0:
        raise ValueError(f"Target-centered scale must be positive for {target}.")
    return _orientation(config, target) * (float(value) - center) / scale


def _robust_location_scale(
    history: pd.Series,
    *,
    mad_constant: float,
    minimum_history: int,
) -> tuple[float, float] | None:
    values = pd.to_numeric(history, errors="coerce")
    values = values[np.isfinite(values.to_numpy(dtype=float))]
    if len(values) < minimum_history:
        return None
    median = float(values.median())
    mad = float((values - median).abs().median())
    scale = float(mad_constant * mad)
    if not math.isfinite(scale) or scale <= 1.0e-12:
        return None
    return median, scale


def transform_target_interval(
    *,
    target: str,
    point: float,
    lower: float,
    upper: float,
    history: pd.Series,
    config: Mapping[str, Any],
    plan: ProspectiveShadowPlan,
) -> dict[str, Any]:
    location_scale = _robust_location_scale(
        history,
        mad_constant=plan.robust_mad_constant,
        minimum_history=plan.robust_minimum_history,
    )
    orientation = _orientation(config, target)
    if location_scale is None:
        method = "target_centered_fallback"
        transform = lambda value: _fallback_transform(float(value), target, config)
        history_count = int(pd.to_numeric(history, errors="coerce").notna().sum())
        center = None
        scale = None
    else:
        method = "expanding_robust_z"
        center, scale = location_scale
        transform = lambda value: orientation * (float(value) - center) / scale
        history_count = int(pd.to_numeric(history, errors="coerce").notna().sum())

    values = [
        float(np.clip(transform(point), -plan.robust_clip, plan.robust_clip)),
        float(np.clip(transform(lower), -plan.robust_clip, plan.robust_clip)),
        float(np.clip(transform(upper), -plan.robust_clip, plan.robust_clip)),
    ]
    transformed_point = values[0]
    transformed_lower = min(values[1], values[2])
    transformed_upper = max(values[1], values[2])
    return {
        "target": target,
        "score": transformed_point,
        "lower_score": transformed_lower,
        "upper_score": transformed_upper,
        "normalization_method": method,
        "history_count": history_count,
        "center": center,
        "scale": scale,
        "orientation": orientation,
    }


def _dimension_label(
    dimension: str,
    score: float,
    config: Mapping[str, Any],
) -> str:
    labels = config["labels"][dimension]
    for ceiling, label in labels:
        if float(score) <= float(ceiling):
            return str(label)
    return str(labels[-1][1])


def _aggregate_dimension(
    dimension: str,
    transformed: Mapping[str, Mapping[str, Any]],
    weights: Mapping[str, float],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    missing = sorted(set(weights) - set(transformed))
    if missing:
        raise ValueError(f"Missing {dimension} transformed targets: {missing}")
    total_weight = float(sum(float(value) for value in weights.values()))
    if total_weight <= 0.0:
        raise ValueError(f"{dimension} weights must have positive mass.")
    normalised = {key: float(value) / total_weight for key, value in weights.items()}
    score = float(sum(normalised[key] * float(transformed[key]["score"]) for key in normalised))
    lower = float(sum(normalised[key] * float(transformed[key]["lower_score"]) for key in normalised))
    upper = float(sum(normalised[key] * float(transformed[key]["upper_score"]) for key in normalised))
    lower, upper = min(lower, upper), max(lower, upper)
    width = max(0.0, upper - lower)
    confidence = float(np.clip(100.0 * (1.0 - width / (2.0 * 2.0)), 0.0, 100.0))
    return {
        "dimension": dimension,
        "score": score,
        "lower_score": lower,
        "upper_score": upper,
        "label": _dimension_label(dimension, score, config),
        "confidence": confidence,
        "component_weights": normalised,
        "components": {key: dict(transformed[key]) for key in normalised},
    }


def build_source_dimensions(
    *,
    history_inputs: pd.DataFrame,
    current_inputs: pd.DataFrame,
    config: Mapping[str, Any],
    plan: ProspectiveShadowPlan,
) -> pd.DataFrame:
    required = {
        "source_target",
        "point_forecast",
        "lower_80",
        "upper_80",
        "source_model_id",
        "source_model_version",
        "source_run_id",
        "information_cutoff",
        "data_as_of",
        "source_hash",
    }
    missing = sorted(required - set(current_inputs.columns))
    if missing:
        raise ValueError(f"Current macro-state inputs are missing columns: {missing}")

    current = current_inputs.copy()
    current["source_target"] = current["source_target"].astype(str)
    if current["source_target"].duplicated().any():
        duplicates = sorted(current.loc[current["source_target"].duplicated(), "source_target"].unique())
        raise ValueError(f"Current source targets must be unique: {duplicates}")

    history = history_inputs.copy()
    if not history.empty:
        if "source_target" not in history or "point_forecast" not in history:
            raise ValueError("Historical inputs require source_target and point_forecast.")
        history["source_target"] = history["source_target"].astype(str)

    transformed: dict[str, dict[str, Any]] = {}
    for row in current.itertuples(index=False):
        target = str(row.source_target)
        prior = (
            history.loc[history["source_target"] == target, "point_forecast"]
            if not history.empty
            else pd.Series(dtype=float)
        )
        transformed[target] = transform_target_interval(
            target=target,
            point=float(row.point_forecast),
            lower=float(row.lower_80),
            upper=float(row.upper_80),
            history=prior,
            config=config,
            plan=plan,
        )

    inflation_weights = config["tournament"]["inflation_weight_candidates"]["policy"]
    labour_weights = config["tournament"]["labour_weight_candidates"]["equal"]
    dimension_specs = {
        "growth": {"GDPC1": 1.0},
        "inflation": inflation_weights,
        "labour": labour_weights,
    }

    rows: list[dict[str, Any]] = []
    for dimension in REQUIRED_DIMENSIONS:
        aggregate = _aggregate_dimension(
            dimension,
            transformed,
            dimension_specs[dimension],
            config,
        )
        component_targets = list(dimension_specs[dimension])
        lineage = current.loc[current["source_target"].isin(component_targets)].copy()
        if lineage.empty:
            raise ValueError(f"No current lineage rows for dimension {dimension}.")
        model_ids = lineage["source_model_id"].dropna().astype(str).unique().tolist()
        model_versions = lineage["source_model_version"].dropna().astype(str).unique().tolist()
        run_ids = lineage["source_run_id"].dropna().astype(str).unique().tolist()
        if len(model_ids) != 1 or len(model_versions) != 1 or len(run_ids) != 1:
            raise ValueError(
                f"{dimension} inputs must share one source model/version/run; "
                f"model_ids={model_ids}, versions={model_versions}, runs={run_ids}"
            )
        cutoff = pd.to_datetime(lineage["information_cutoff"], errors="raise").max().date()
        data_as_of_values = pd.to_datetime(lineage["data_as_of"], errors="coerce").dropna()
        data_as_of = data_as_of_values.max().date() if not data_as_of_values.empty else None
        lineage_payload = lineage[
            [
                "source_target",
                "point_forecast",
                "lower_80",
                "upper_80",
                "information_cutoff",
                "data_as_of",
                "source_hash",
            ]
        ].sort_values("source_target").to_dict(orient="records")
        source_hash = sha256_json(
            {
                "dimension": dimension,
                "candidate_id": plan.source_candidate_id,
                "lineage": lineage_payload,
                "transformation": aggregate["components"],
            }
        )
        rows.append(
            {
                **{key: aggregate[key] for key in (
                    "dimension", "score", "lower_score", "upper_score", "label", "confidence"
                )},
                "source_model_id": model_ids[0],
                "source_model_version": model_versions[0],
                "source_run_id": run_ids[0],
                "source_information_cutoff": cutoff,
                "source_data_as_of": data_as_of,
                "source_hash": source_hash,
                "details_json": canonical_json(
                    {
                        "candidate_id": plan.source_candidate_id,
                        "normalization": "expanding_robust_z",
                        "component_weights": aggregate["component_weights"],
                        "components": aggregate["components"],
                    }
                ),
            }
        )
    return pd.DataFrame(rows)


def classify_sensitive_regime(
    growth: np.ndarray,
    inflation: np.ndarray,
    labour: np.ndarray,
    thresholds: Mapping[str, float],
) -> np.ndarray:
    count = len(growth)
    regime = np.full(count, "mixed_transition", dtype=object)
    remaining = np.ones(count, dtype=bool)

    conditions = [
        (
            "hard_landing_risk",
            (growth <= float(thresholds["hard_growth_max"]))
            & (labour <= float(thresholds["hard_labour_max"])),
        ),
        (
            "stagflation_risk",
            (growth <= float(thresholds["stag_growth_max"]))
            & (inflation >= float(thresholds["stag_inflation_min"])),
        ),
        (
            "overheating",
            (growth >= float(thresholds["overheat_growth_min"]))
            & (inflation >= float(thresholds["overheat_inflation_min"]))
            & (labour >= float(thresholds["overheat_labour_min"])),
        ),
        (
            "disinflationary_expansion",
            (growth >= float(thresholds["disinflation_growth_min"]))
            & (inflation <= float(thresholds["disinflation_inflation_max"]))
            & (labour >= float(thresholds["disinflation_labour_min"])),
        ),
        (
            "balanced_expansion",
            (growth >= float(thresholds["balanced_growth_min"]))
            & (growth <= float(thresholds["balanced_growth_max"]))
            & (inflation >= float(thresholds["balanced_inflation_min"]))
            & (inflation <= float(thresholds["balanced_inflation_max"]))
            & (labour >= float(thresholds["balanced_labour_min"]))
            & (labour <= float(thresholds["balanced_labour_max"])),
        ),
        (
            "reflation",
            (growth >= float(thresholds["reflation_growth_min"]))
            & (inflation >= float(thresholds["reflation_inflation_min"])),
        ),
        (
            "demand_slowdown",
            (growth <= float(thresholds["slowdown_growth_max"]))
            & (inflation <= float(thresholds["slowdown_inflation_max"])),
        ),
    ]
    for label, condition in conditions:
        selected = remaining & condition
        regime[selected] = label
        remaining[selected] = False
    return regime


def source_family_probabilities(
    dimensions: pd.DataFrame,
    *,
    state_date: date,
    config: Mapping[str, Any],
    plan: ProspectiveShadowPlan,
) -> dict[str, float]:
    required = {"dimension", "score", "lower_score", "upper_score"}
    missing = sorted(required - set(dimensions.columns))
    if missing:
        raise ValueError(f"Dimension frame is missing columns: {missing}")
    indexed = dimensions.set_index("dimension")
    if set(indexed.index.astype(str)) != set(REQUIRED_DIMENSIONS):
        raise ValueError("Dimension frame must contain growth, inflation, and labour.")

    seed = int(plan.random_seed + pd.Period(state_date, freq="M").ordinal)
    rng = np.random.default_rng(seed)
    draws: dict[str, np.ndarray] = {}
    for dimension in REQUIRED_DIMENSIONS:
        row = indexed.loc[dimension]
        mean = float(row["score"])
        lower = float(row["lower_score"])
        upper = float(row["upper_score"])
        sigma = max(0.0, upper - lower) / (2.0 * plan.normal_interval_z)
        if sigma <= 1.0e-12:
            values = np.full(plan.uncertainty_draws, mean, dtype=float)
        else:
            values = rng.normal(mean, sigma, plan.uncertainty_draws)
        draws[dimension] = np.clip(values, -plan.robust_clip, plan.robust_clip)

    thresholds = config["tournament"]["threshold_candidates"]["sensitive"]
    regimes = classify_sensitive_regime(
        draws["growth"],
        draws["inflation"],
        draws["labour"],
        thresholds,
    )
    families = np.asarray([REGIME_TO_FAMILY[str(item)] for item in regimes], dtype=object)
    counts = {family: float(np.sum(families == family)) for family in plan.family_order}
    return normalise_probability_vector(counts, plan)


def rolling_frequency_probabilities(
    history: pd.DataFrame,
    *,
    information_cutoff: date,
    state_date: date,
    plan: ProspectiveShadowPlan,
) -> tuple[dict[str, float], pd.DataFrame]:
    required = {"state_date", "primary_family", "state_available_date"}
    missing = sorted(required - set(history.columns))
    if missing:
        raise ValueError(f"Rolling-frequency history is missing columns: {missing}")

    frame = history.copy()
    frame["state_date"] = pd.to_datetime(frame["state_date"], errors="raise").dt.date
    frame["state_available_date"] = pd.to_datetime(
        frame["state_available_date"], errors="raise"
    ).dt.date
    frame["primary_family"] = frame["primary_family"].astype(str)
    frame = frame.loc[
        (frame["state_date"] < state_date)
        & (frame["state_available_date"] <= information_cutoff)
    ].copy()
    frame = frame.sort_values(["state_date", "state_available_date"])
    frame = frame.drop_duplicates("state_date", keep="last")
    frame = frame.tail(plan.rolling_window_months)
    if frame.empty:
        raise ValueError(
            "No fixed-horizon target history was available by the information cutoff."
        )
    invalid = sorted(set(frame["primary_family"]) - set(plan.family_order))
    if invalid:
        raise ValueError(f"Rolling-frequency history contains invalid families: {invalid}")
    counts = frame["primary_family"].value_counts()
    probabilities = {
        family: float(counts.get(family, 0.0))
        for family in plan.family_order
    }
    return normalise_probability_vector(probabilities, plan), frame.reset_index(drop=True)


def prediction_rows(
    *,
    shadow_run_id: str,
    model_version: str,
    state_date: date,
    information_cutoff: date,
    prediction_timestamp: pd.Timestamp,
    probability_vectors: Mapping[str, Mapping[str, float]],
    plan: ProspectiveShadowPlan,
    created_at: pd.Timestamp,
) -> pd.DataFrame:
    if set(probability_vectors) != set(REQUIRED_BENCHMARKS):
        raise ValueError("Exactly source and rolling_frequency vectors are required.")
    rows = []
    for benchmark_id in REQUIRED_BENCHMARKS:
        diagnostics = probability_diagnostics(probability_vectors[benchmark_id], plan)
        rows.append(
            {
                "shadow_run_id": shadow_run_id,
                "model_version": model_version,
                "state_date": state_date,
                "information_cutoff": information_cutoff,
                "prediction_timestamp": prediction_timestamp,
                "benchmark_id": benchmark_id,
                **diagnostics,
                "no_look_ahead_pass": True,
                "created_at": created_at,
            }
        )
    return pd.DataFrame(rows)


def information_set_hash(
    *,
    current_inputs: pd.DataFrame,
    source_dimensions: pd.DataFrame,
    rolling_history: pd.DataFrame,
    plan: ProspectiveShadowPlan,
) -> str:
    input_columns = [
        "source_model_id",
        "source_model_version",
        "source_run_id",
        "source_target",
        "point_forecast",
        "lower_80",
        "upper_80",
        "information_cutoff",
        "data_as_of",
        "source_hash",
    ]
    dimension_columns = [
        "dimension",
        "score",
        "lower_score",
        "upper_score",
        "source_hash",
    ]
    history_columns = ["state_date", "primary_family", "state_available_date"]
    return sha256_json(
        {
            "candidate_id": plan.source_candidate_id,
            "source_inputs": current_inputs[input_columns]
            .sort_values("source_target")
            .to_dict(orient="records"),
            "source_dimensions": source_dimensions[dimension_columns]
            .sort_values("dimension")
            .to_dict(orient="records"),
            "rolling_history": rolling_history[history_columns]
            .sort_values("state_date")
            .to_dict(orient="records"),
        }
    )
