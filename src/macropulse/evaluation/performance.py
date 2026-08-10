from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from macropulse.evaluation.ledger import (
    PRODUCTION_COMPONENTS,
    summarise_forecast_evaluation,
    target_specs,
)


PERFORMANCE_SCHEMA_VERSION = "1.0.0"
NOMINAL_INTERVAL_COVERAGE = 0.80
MIN_INTERPRETATION_N = 8
DRIFT_RECENT_N = 4
DRIFT_REFERENCE_N = 8

TARGET_METRIC_COLUMNS = [
    "component",
    "target_series",
    "target_name",
    "target_transform",
    "n_resolved",
    "sample_status",
    "first_information_cutoff",
    "last_information_cutoff",
    "mae",
    "rmse",
    "bias",
    "median_absolute_error",
    "n_interval",
    "interval_coverage_80",
    "coverage_gap_vs_nominal_80",
    "mean_interval_width",
    "median_interval_width",
    "n_direction",
    "directional_accuracy",
    "mean_lead_days",
    "median_lead_days",
]

STAGE_METRIC_COLUMNS = [
    "component",
    "target_series",
    "target_name",
    "forecast_stage",
    *TARGET_METRIC_COLUMNS[4:],
]

HORIZON_METRIC_COLUMNS = [
    "component",
    "target_series",
    "target_name",
    "horizon_bucket",
    *TARGET_METRIC_COLUMNS[4:],
]

DRIFT_COLUMNS = [
    "component",
    "target_series",
    "target_name",
    "drift_status",
    "total_resolved",
    "required_resolved",
    "recent_n",
    "reference_n",
    "recent_start_cutoff",
    "recent_end_cutoff",
    "reference_start_cutoff",
    "reference_end_cutoff",
    "recent_mae",
    "reference_mae",
    "mae_ratio_recent_to_reference",
    "recent_bias",
    "reference_bias",
    "bias_shift",
    "recent_interval_coverage_80",
    "reference_interval_coverage_80",
    "coverage_shift",
]


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    result = float(value)
    if not np.isfinite(result):
        return None
    return result


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return pd.Timestamp(value).date()


def _finite_series(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.loc[np.isfinite(values.to_numpy(dtype=float))]


def _mean(values: pd.Series) -> float | None:
    if values.empty:
        return None
    return float(values.mean())


def _median(values: pd.Series) -> float | None:
    if values.empty:
        return None
    return float(values.median())


def _rmse(values: pd.Series) -> float | None:
    if values.empty:
        return None
    array = values.to_numpy(dtype=float)
    return float(np.sqrt(np.mean(np.square(array))))


def _sample_status(n: int) -> str:
    if n < MIN_INTERPRETATION_N:
        return "insufficient_for_interpretation"
    return "descriptive_ready"


def _direction_applicable(transform: str) -> bool:
    return str(transform).strip().lower() != "level"


def _resolved_rows(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return ledger.copy()

    required = {
        "evaluation_status",
        "no_look_ahead_pass",
        "component",
        "target_series",
        "target_name",
        "information_cutoff",
        "forecast_value",
        "outcome_value",
        "absolute_error",
        "signed_error",
        "squared_error",
        "interval_covered",
        "interval_width",
        "lead_days",
        "forecast_stage",
    }
    missing = sorted(required - set(ledger.columns))
    if missing:
        raise ValueError(
            "Phase 3C ledger input is missing required columns: "
            + ", ".join(missing)
        )

    resolved = ledger.loc[
        ledger["evaluation_status"].astype(str).eq("resolved")
        & ledger["no_look_ahead_pass"].eq(True)
    ].copy()

    if resolved.empty:
        return resolved

    resolved["information_cutoff"] = pd.to_datetime(
        resolved["information_cutoff"],
        errors="coerce",
    )
    return resolved.sort_values(
        [
            "component",
            "target_series",
            "information_cutoff",
            "target_period",
            "run_id",
        ],
        kind="stable",
    ).reset_index(drop=True)


def _metric_row(
    frame: pd.DataFrame,
    *,
    component: str,
    target_series: str,
    target_name: str,
    target_transform: str,
) -> dict[str, Any]:
    absolute = _finite_series(frame, "absolute_error")
    signed = _finite_series(frame, "signed_error")
    squared = _finite_series(frame, "squared_error")
    widths = _finite_series(frame, "interval_width")
    lead_days = _finite_series(frame, "lead_days")

    interval_values = frame["interval_covered"].dropna()
    interval_values = interval_values.loc[
        interval_values.map(lambda value: isinstance(value, (bool, np.bool_)))
    ]
    interval_coverage = (
        float(interval_values.astype(bool).mean())
        if not interval_values.empty
        else None
    )

    n_direction = 0
    directional_accuracy: float | None = None
    if _direction_applicable(target_transform):
        forecast = pd.to_numeric(frame["forecast_value"], errors="coerce")
        outcome = pd.to_numeric(frame["outcome_value"], errors="coerce")
        valid = forecast.notna() & outcome.notna()
        if valid.any():
            forecast_array = forecast.loc[valid].to_numpy(dtype=float)
            outcome_array = outcome.loc[valid].to_numpy(dtype=float)
            finite = np.isfinite(forecast_array) & np.isfinite(outcome_array)
            if finite.any():
                forecast_array = forecast_array[finite]
                outcome_array = outcome_array[finite]
                n_direction = int(len(forecast_array))
                directional_accuracy = float(
                    np.mean(np.sign(forecast_array) == np.sign(outcome_array))
                )

    first_cutoff = (
        _to_date(frame["information_cutoff"].min())
        if not frame.empty
        else None
    )
    last_cutoff = (
        _to_date(frame["information_cutoff"].max())
        if not frame.empty
        else None
    )

    n_resolved = int(len(frame))
    return {
        "component": component,
        "target_series": target_series,
        "target_name": target_name,
        "target_transform": target_transform,
        "n_resolved": n_resolved,
        "sample_status": _sample_status(n_resolved),
        "first_information_cutoff": first_cutoff,
        "last_information_cutoff": last_cutoff,
        "mae": _mean(absolute),
        "rmse": _rmse(signed) if squared.empty else float(np.sqrt(squared.mean())),
        "bias": _mean(signed),
        "median_absolute_error": _median(absolute),
        "n_interval": int(len(interval_values)),
        "interval_coverage_80": interval_coverage,
        "coverage_gap_vs_nominal_80": (
            float(interval_coverage - NOMINAL_INTERVAL_COVERAGE)
            if interval_coverage is not None
            else None
        ),
        "mean_interval_width": _mean(widths),
        "median_interval_width": _median(widths),
        "n_direction": n_direction,
        "directional_accuracy": directional_accuracy,
        "mean_lead_days": _mean(lead_days),
        "median_lead_days": _median(lead_days),
    }


def _target_metadata() -> dict[tuple[str, str], dict[str, str]]:
    metadata: dict[tuple[str, str], dict[str, str]] = {}
    for (component, series_id), target in target_specs().items():
        metadata[(component, series_id)] = {
            "target_name": target.name,
            "target_transform": target.transform,
        }
    return metadata


def build_target_metrics(ledger: pd.DataFrame) -> pd.DataFrame:
    resolved = _resolved_rows(ledger)
    if resolved.empty:
        return pd.DataFrame(columns=TARGET_METRIC_COLUMNS)

    metadata = _target_metadata()
    records: list[dict[str, Any]] = []

    for (component, target_series), frame in resolved.groupby(
        ["component", "target_series"],
        sort=True,
    ):
        key = (str(component), str(target_series))
        details = metadata.get(key)
        if details is None:
            raise ValueError(
                "Resolved ledger target is outside governed target contract: "
                f"{key[0]}/{key[1]}"
            )

        row = _metric_row(
            frame,
            component=key[0],
            target_series=key[1],
            target_name=details["target_name"],
            target_transform=details["target_transform"],
        )
        records.append(row)

    return pd.DataFrame.from_records(
        records,
        columns=TARGET_METRIC_COLUMNS,
    ).sort_values(
        ["component", "target_series"],
        kind="stable",
    ).reset_index(drop=True)


def build_stage_metrics(ledger: pd.DataFrame) -> pd.DataFrame:
    resolved = _resolved_rows(ledger)
    if resolved.empty:
        return pd.DataFrame(columns=STAGE_METRIC_COLUMNS)

    metadata = _target_metadata()
    frame = resolved.copy()
    frame["forecast_stage"] = frame["forecast_stage"].fillna("UNKNOWN").astype(str)

    records: list[dict[str, Any]] = []
    for (component, target_series, stage), group in frame.groupby(
        ["component", "target_series", "forecast_stage"],
        sort=True,
    ):
        key = (str(component), str(target_series))
        details = metadata[key]
        metric = _metric_row(
            group,
            component=key[0],
            target_series=key[1],
            target_name=details["target_name"],
            target_transform=details["target_transform"],
        )
        metric.pop("target_transform")
        metric["forecast_stage"] = str(stage)
        records.append(metric)

    return pd.DataFrame.from_records(
        records,
        columns=STAGE_METRIC_COLUMNS,
    ).sort_values(
        ["component", "target_series", "forecast_stage"],
        kind="stable",
    ).reset_index(drop=True)


def horizon_bucket(value: Any) -> str:
    lead = _to_float(value)
    if lead is None:
        return "UNKNOWN"
    if lead < 0:
        return "INVALID_NEGATIVE"
    if lead <= 7:
        return "0-7d"
    if lead <= 14:
        return "8-14d"
    if lead <= 30:
        return "15-30d"
    if lead <= 60:
        return "31-60d"
    return "61+d"


def build_horizon_metrics(ledger: pd.DataFrame) -> pd.DataFrame:
    resolved = _resolved_rows(ledger)
    if resolved.empty:
        return pd.DataFrame(columns=HORIZON_METRIC_COLUMNS)

    metadata = _target_metadata()
    frame = resolved.copy()
    frame["horizon_bucket"] = frame["lead_days"].map(horizon_bucket)

    records: list[dict[str, Any]] = []
    for (component, target_series, bucket), group in frame.groupby(
        ["component", "target_series", "horizon_bucket"],
        sort=True,
    ):
        key = (str(component), str(target_series))
        details = metadata[key]
        metric = _metric_row(
            group,
            component=key[0],
            target_series=key[1],
            target_name=details["target_name"],
            target_transform=details["target_transform"],
        )
        metric.pop("target_transform")
        metric["horizon_bucket"] = str(bucket)
        records.append(metric)

    return pd.DataFrame.from_records(
        records,
        columns=HORIZON_METRIC_COLUMNS,
    ).sort_values(
        ["component", "target_series", "horizon_bucket"],
        kind="stable",
    ).reset_index(drop=True)


def _window_mae(frame: pd.DataFrame) -> float | None:
    return _mean(_finite_series(frame, "absolute_error"))


def _window_bias(frame: pd.DataFrame) -> float | None:
    return _mean(_finite_series(frame, "signed_error"))


def _window_coverage(frame: pd.DataFrame) -> float | None:
    values = frame["interval_covered"].dropna()
    values = values.loc[
        values.map(lambda value: isinstance(value, (bool, np.bool_)))
    ]
    if values.empty:
        return None
    return float(values.astype(bool).mean())


def _difference(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return float(left - right)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator == 0.0:
        return None
    return float(numerator / denominator)


def build_drift_metrics(ledger: pd.DataFrame) -> pd.DataFrame:
    resolved = _resolved_rows(ledger)
    if resolved.empty:
        return pd.DataFrame(columns=DRIFT_COLUMNS)

    metadata = _target_metadata()
    required = DRIFT_RECENT_N + DRIFT_REFERENCE_N
    records: list[dict[str, Any]] = []

    for (component, target_series), frame in resolved.groupby(
        ["component", "target_series"],
        sort=True,
    ):
        key = (str(component), str(target_series))
        details = metadata[key]
        ordered = frame.sort_values(
            ["information_cutoff", "target_period", "run_id"],
            kind="stable",
        ).reset_index(drop=True)

        total = int(len(ordered))
        base: dict[str, Any] = {
            "component": key[0],
            "target_series": key[1],
            "target_name": details["target_name"],
            "drift_status": "insufficient_sample",
            "total_resolved": total,
            "required_resolved": required,
            "recent_n": min(total, DRIFT_RECENT_N),
            "reference_n": max(min(total - DRIFT_RECENT_N, DRIFT_REFERENCE_N), 0),
            "recent_start_cutoff": None,
            "recent_end_cutoff": None,
            "reference_start_cutoff": None,
            "reference_end_cutoff": None,
            "recent_mae": None,
            "reference_mae": None,
            "mae_ratio_recent_to_reference": None,
            "recent_bias": None,
            "reference_bias": None,
            "bias_shift": None,
            "recent_interval_coverage_80": None,
            "reference_interval_coverage_80": None,
            "coverage_shift": None,
        }

        if total < required:
            records.append(base)
            continue

        recent = ordered.tail(DRIFT_RECENT_N)
        reference = ordered.iloc[
            -(DRIFT_RECENT_N + DRIFT_REFERENCE_N):-DRIFT_RECENT_N
        ]

        recent_mae = _window_mae(recent)
        reference_mae = _window_mae(reference)
        recent_bias = _window_bias(recent)
        reference_bias = _window_bias(reference)
        recent_coverage = _window_coverage(recent)
        reference_coverage = _window_coverage(reference)

        base.update(
            {
                "drift_status": "descriptive_available",
                "recent_n": int(len(recent)),
                "reference_n": int(len(reference)),
                "recent_start_cutoff": _to_date(recent["information_cutoff"].min()),
                "recent_end_cutoff": _to_date(recent["information_cutoff"].max()),
                "reference_start_cutoff": _to_date(
                    reference["information_cutoff"].min()
                ),
                "reference_end_cutoff": _to_date(
                    reference["information_cutoff"].max()
                ),
                "recent_mae": recent_mae,
                "reference_mae": reference_mae,
                "mae_ratio_recent_to_reference": _ratio(
                    recent_mae,
                    reference_mae,
                ),
                "recent_bias": recent_bias,
                "reference_bias": reference_bias,
                "bias_shift": _difference(recent_bias, reference_bias),
                "recent_interval_coverage_80": recent_coverage,
                "reference_interval_coverage_80": reference_coverage,
                "coverage_shift": _difference(
                    recent_coverage,
                    reference_coverage,
                ),
            }
        )
        records.append(base)

    return pd.DataFrame.from_records(
        records,
        columns=DRIFT_COLUMNS,
    ).sort_values(
        ["component", "target_series"],
        kind="stable",
    ).reset_index(drop=True)


def build_performance_tables(
    ledger: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    return {
        "target_metrics": build_target_metrics(ledger),
        "stage_metrics": build_stage_metrics(ledger),
        "horizon_metrics": build_horizon_metrics(ledger),
        "drift_metrics": build_drift_metrics(ledger),
    }


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {key: _json_value(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def serialise_performance_report(
    ledger: pd.DataFrame,
    *,
    as_of: date,
) -> dict[str, Any]:
    evaluation_summary = summarise_forecast_evaluation(
        ledger,
        as_of=as_of,
    )
    tables = build_performance_tables(ledger)

    resolved_targets = (
        int(tables["target_metrics"]["target_series"].nunique())
        if not tables["target_metrics"].empty
        else 0
    )
    drift_available = (
        int(
            tables["drift_metrics"]["drift_status"]
            .astype(str)
            .eq("descriptive_available")
            .sum()
        )
        if not tables["drift_metrics"].empty
        else 0
    )

    summary = {
        "as_of": as_of,
        "forecast_rows": int(evaluation_summary["forecast_rows"]),
        "resolved_rows": int(evaluation_summary["resolved_rows"]),
        "unresolved_rows": int(evaluation_summary["unresolved_rows"]),
        "invalid_rows": int(evaluation_summary["invalid_rows"]),
        "resolved_target_series": resolved_targets,
        "targets_with_descriptive_drift": drift_available,
    }

    policy = {
        "nominal_interval_coverage": NOMINAL_INTERVAL_COVERAGE,
        "minimum_interpretation_sample": MIN_INTERPRETATION_N,
        "drift_recent_window": DRIFT_RECENT_N,
        "drift_reference_window": DRIFT_REFERENCE_N,
        "drift_classification": "descriptive_only",
        "cross_target_raw_error_pooling": False,
        "automatic_model_action": False,
        "model1d_included": False,
    }

    return {
        "schema_version": PERFORMANCE_SCHEMA_VERSION,
        "summary": {
            key: _json_value(value)
            for key, value in summary.items()
        },
        "policy": policy,
        "target_metrics": _records(tables["target_metrics"]),
        "stage_metrics": _records(tables["stage_metrics"]),
        "horizon_metrics": _records(tables["horizon_metrics"]),
        "drift_metrics": _records(tables["drift_metrics"]),
    }
