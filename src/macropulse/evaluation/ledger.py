from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from macropulse.config import get_series_definitions, load_registry
from macropulse.data.repository import MacroRepository
from macropulse.inflation.config import (
    target_definitions as inflation_target_definitions,
)
from macropulse.labour.config import (
    target_definitions as labour_target_definitions,
)
from macropulse.labour.vintage import structural_missing_reason
from macropulse.processing.transforms import transform_series


PRODUCTION_COMPONENTS = ("1A", "1B", "1C")
OUTCOME_VINTAGE = "first_release"
OUTCOME_DEFINITION = "initial_release_transformed_target"
SIGNED_ERROR_CONVENTION = "forecast_minus_outcome"

EVALUATION_COLUMNS = [
    "evaluation_id",
    "forecast_identity",
    "evaluation_as_of",
    "component",
    "model_id",
    "model_version",
    "run_id",
    "information_cutoff",
    "data_as_of",
    "target_series",
    "target_name",
    "target_period",
    "forecast_stage",
    "forecast_model_name",
    "forecast_value",
    "lower_80",
    "upper_80",
    "interval_width",
    "estimated_release_date",
    "outcome_definition",
    "outcome_vintage",
    "outcome_evidence_source",
    "outcome_release_date",
    "outcome_value",
    "evaluation_status",
    "status_detail",
    "no_look_ahead_pass",
    "lead_days",
    "signed_error",
    "absolute_error",
    "squared_error",
    "interval_covered",
]


@dataclass(frozen=True)
class ProductionSpec:
    component: str
    model_id: str
    model_version: str


@dataclass(frozen=True)
class TargetSpec:
    component: str
    series_id: str
    name: str
    frequency: str
    transform: str
    start_date: str


@dataclass(frozen=True)
class OutcomeResolution:
    status: str
    detail: str
    release_date: date | None
    value: float | None
    evidence_source: str | None = None


def _to_date(value: Any) -> date | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date()


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    result = float(value)
    if not np.isfinite(result):
        return None
    return result


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_phase3_boundary(project_root: Path) -> dict[str, Any]:
    path = project_root / "PHASE3_BOUNDARY.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("phase") != "III":
        raise ValueError("PHASE3_BOUNDARY.json must declare Phase III.")
    if payload.get("phase3_may_mutate_governed_forecasts") is not False:
        raise ValueError("Phase III governed-forecast mutation boundary changed.")
    if payload.get("phase3_may_tune_model1d_on_prospective_outcomes") is not False:
        raise ValueError("Phase III Model 1D tuning boundary changed.")
    return payload


def production_specs(project_root: Path) -> dict[str, ProductionSpec]:
    boundary = load_phase3_boundary(project_root)
    suite = boundary.get("model_suite")
    if not isinstance(suite, dict):
        raise ValueError("PHASE3_BOUNDARY.json must contain model_suite.")

    expected_ids = {
        "1A": "US_GDP_NOWCAST_1A",
        "1B": "US_INFLATION_NOWCAST_1B",
        "1C": "US_LABOUR_NOWCAST_1C",
    }
    specs: dict[str, ProductionSpec] = {}
    for component in PRODUCTION_COMPONENTS:
        item = suite.get(component)
        if not isinstance(item, dict):
            raise ValueError(f"Missing Phase III model boundary for {component}.")
        if item.get("status") != "production":
            raise ValueError(f"{component} is not declared production.")
        version = str(item.get("version", ""))
        if version != "1.0.0":
            raise ValueError(
                f"{component} version changed from governed production v1.0.0."
            )
        specs[component] = ProductionSpec(
            component=component,
            model_id=expected_ids[component],
            model_version=version,
        )
    return specs


def target_specs() -> dict[tuple[str, str], TargetSpec]:
    specs: dict[tuple[str, str], TargetSpec] = {}

    registry = load_registry()
    target_series = str(registry["model"]["target_series"])
    gdp_map = {item.series_id: item for item in get_series_definitions()}
    if target_series not in gdp_map:
        raise ValueError(f"Unknown governed GDP target: {target_series}")
    gdp = gdp_map[target_series]
    specs[("1A", gdp.series_id)] = TargetSpec(
        component="1A",
        series_id=gdp.series_id,
        name=gdp.name,
        frequency=gdp.frequency,
        transform=gdp.transform,
        start_date=gdp.start_date,
    )

    for definition in inflation_target_definitions():
        specs[("1B", definition.series_id)] = TargetSpec(
            component="1B",
            series_id=definition.series_id,
            name=definition.name,
            frequency=definition.frequency,
            transform=definition.transform,
            start_date=definition.start_date,
        )

    for definition in labour_target_definitions():
        specs[("1C", definition.series_id)] = TargetSpec(
            component="1C",
            series_id=definition.series_id,
            name=definition.name,
            frequency=definition.frequency,
            transform=definition.transform,
            start_date=definition.start_date,
        )
    return specs


def _empty_forecasts() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "component",
            "run_id",
            "model_id",
            "model_version",
            "information_cutoff",
            "data_as_of",
            "target_series",
            "target_name",
            "target_period",
            "forecast_stage",
            "forecast_model_name",
            "forecast_value",
            "lower_80",
            "upper_80",
            "estimated_release_date",
            "created_at",
        ]
    )


def _gdp_forecasts(
    repository: MacroRepository,
    *,
    spec: ProductionSpec,
    as_of: date,
    targets: dict[tuple[str, str], TargetSpec],
) -> pd.DataFrame:
    frame = repository.query_df(
        """
        SELECT run_id, model_id, model_version, information_cutoff, data_as_of,
               target_period, forecast_stage,
               champion_model AS forecast_model_name,
               production_forecast AS forecast_value,
               lower_80, upper_80, created_at
        FROM forecast_registry
        WHERE model_id = ?
          AND model_version = ?
          AND status = 'success'
          AND information_cutoff <= ?
        ORDER BY information_cutoff, created_at, run_id
        """,
        [spec.model_id, spec.model_version, as_of],
    )
    if frame.empty:
        return _empty_forecasts()

    candidates = [
        target for (component, _), target in targets.items() if component == "1A"
    ]
    if len(candidates) != 1:
        raise ValueError("Model 1A must have exactly one governed target.")
    target = candidates[0]
    frame = frame.copy()
    frame.insert(0, "component", "1A")
    frame["target_series"] = target.series_id
    frame["target_name"] = target.name
    frame["estimated_release_date"] = None
    return frame[_empty_forecasts().columns]


def _monthly_live_forecasts(
    repository: MacroRepository,
    *,
    component: str,
    spec: ProductionSpec,
    as_of: date,
) -> pd.DataFrame:
    if component == "1B":
        run_table = "inflation_live_runs"
        forecast_table = "inflation_live_forecasts"
    elif component == "1C":
        run_table = "labour_live_runs"
        forecast_table = "labour_live_forecasts"
    else:
        raise ValueError(f"Unsupported monthly production component: {component}")

    frame = repository.query_df(
        f"""
        SELECT f.run_id, r.model_id, r.model_version,
               r.information_cutoff, r.data_as_of,
               f.target_series, f.target_name, f.target_period,
               f.forecast_stage,
               f.stable_model_name AS forecast_model_name,
               f.stable_point_forecast AS forecast_value,
               f.lower_80, f.upper_80, f.estimated_release_date,
               f.created_at
        FROM {run_table} AS r
        JOIN {forecast_table} AS f
          ON r.run_id = f.run_id
        WHERE r.model_id = ?
          AND r.model_version = ?
          AND r.status = 'success'
          AND r.information_cutoff <= ?
        ORDER BY r.information_cutoff, f.target_series, f.created_at, f.run_id
        """,
        [spec.model_id, spec.model_version, as_of],
    )
    if frame.empty:
        return _empty_forecasts()
    frame = frame.copy()
    frame.insert(0, "component", component)
    return frame[_empty_forecasts().columns]


def collect_governed_forecasts(
    repository: MacroRepository,
    *,
    as_of: date,
    project_root: Path,
) -> pd.DataFrame:
    if as_of > date.today():
        raise ValueError("Evaluation as-of date cannot be in the future.")

    specs = production_specs(project_root)
    targets = target_specs()
    frames = [
        _gdp_forecasts(
            repository,
            spec=specs["1A"],
            as_of=as_of,
            targets=targets,
        ),
        _monthly_live_forecasts(
            repository,
            component="1B",
            spec=specs["1B"],
            as_of=as_of,
        ),
        _monthly_live_forecasts(
            repository,
            component="1C",
            spec=specs["1C"],
            as_of=as_of,
        ),
    ]
    nonempty = [frame for frame in frames if not frame.empty]
    if not nonempty:
        return _empty_forecasts()
    records = [
        record
        for frame in nonempty
        for record in frame.to_dict(orient="records")
    ]
    result = pd.DataFrame.from_records(
        records,
        columns=_empty_forecasts().columns,
    )
    return result.sort_values(
        ["component", "information_cutoff", "target_series", "run_id"],
        kind="stable",
    ).reset_index(drop=True)


def _period_for_target(target: TargetSpec, target_period: str) -> pd.Period:
    frequency = target.frequency.upper()
    if frequency.startswith("Q"):
        return pd.Period(str(target_period), freq="Q")
    if frequency.startswith("M"):
        return pd.Period(str(target_period), freq="M")
    raise ValueError(
        f"Unsupported target frequency for evaluation: "
        f"{target.series_id}={target.frequency}"
    )


def _actual_from_release_snapshot(
    snapshot: pd.DataFrame,
    *,
    target: TargetSpec,
    target_period: pd.Period,
) -> float:
    rows = snapshot.loc[
        snapshot["series_id"].astype(str) == target.series_id
    ].copy()
    if rows.empty:
        raise ValueError(
            f"No release-date snapshot rows exist for {target.series_id}."
        )

    rows["observation_date"] = pd.to_datetime(
        rows["observation_date"],
        errors="coerce",
    )
    rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
    rows = (
        rows.dropna(subset=["observation_date", "value"])
        .sort_values("observation_date", kind="stable")
        .drop_duplicates("observation_date", keep="last")
    )
    if rows.empty:
        raise ValueError(
            f"No usable release-date snapshot values exist for "
            f"{target.series_id}."
        )

    series = pd.Series(
        rows["value"].to_numpy(dtype=float),
        index=rows["observation_date"],
        name=target.series_id,
    )
    frequency = target.frequency.upper()
    if frequency.startswith("Q"):
        series.index = series.index.to_period("Q")
    elif frequency.startswith("M"):
        series.index = series.index.to_period("M")
    else:
        raise ValueError(
            f"Unsupported target frequency for outcome transform: "
            f"{target.series_id}={target.frequency}"
        )

    levels = series.groupby(level=0).last().sort_index()
    transformed = transform_series(levels, target.transform).dropna()
    if target_period not in transformed.index:
        raise ValueError(
            f"No transformed release-date outcome is available for "
            f"{target.series_id} {target_period}."
        )

    value = float(transformed.loc[target_period])
    if not np.isfinite(value):
        raise ValueError(
            f"Non-finite release-date outcome for "
            f"{target.series_id} {target_period}."
        )
    return value


def _initial_vintage_rows(
    repository: MacroRepository,
    *,
    target: TargetSpec,
    target_period: pd.Period,
) -> pd.DataFrame:
    return repository.query_df(
        """
        SELECT series_id, observation_date, realtime_start, realtime_end,
               value, vintage_type, retrieved_at, source
        FROM observations
        WHERE series_id = ?
          AND vintage_type = 'initial'
          AND observation_date <= ?
        ORDER BY observation_date, realtime_start, retrieved_at
        """,
        [target.series_id, target_period.end_time.date()],
    )


def _target_initial_release_date(
    initial_rows: pd.DataFrame,
    *,
    target_period: pd.Period,
) -> date | None:
    if initial_rows.empty:
        return None

    observation_dates = pd.to_datetime(
        initial_rows["observation_date"],
        errors="coerce",
    )
    starts = pd.to_datetime(
        initial_rows["realtime_start"],
        errors="coerce",
    )
    mask = (
        (observation_dates.dt.date >= target_period.start_time.date())
        & (observation_dates.dt.date <= target_period.end_time.date())
    )
    candidates = starts.loc[mask].dropna()
    if candidates.empty:
        return None
    return candidates.min().date()


def resolve_first_release_outcome(
    repository: MacroRepository,
    *,
    target: TargetSpec,
    target_period: str,
    as_of: date,
    expected_release_date: date | None = None,
) -> OutcomeResolution:
    period = _period_for_target(target, target_period)

    if target.component == "1C":
        structural_reason = structural_missing_reason(target.series_id, period)
        if structural_reason is not None:
            return OutcomeResolution(
                status="structurally_unavailable",
                detail=structural_reason,
                release_date=None,
                value=None,
                evidence_source=None,
            )

    initial_rows = _initial_vintage_rows(
        repository,
        target=target,
        target_period=period,
    )
    release_date = _target_initial_release_date(
        initial_rows,
        target_period=period,
    )

    if release_date is None:
        if period.end_time.date() > as_of:
            return OutcomeResolution(
                status="unresolved_outcome_not_yet_available",
                detail=(
                    f"Target period {period} has not ended by evaluation "
                    f"as-of {as_of.isoformat()}."
                ),
                release_date=None,
                value=None,
                evidence_source=None,
            )

        expected = _to_date(expected_release_date)
        if expected is not None and expected > as_of:
            return OutcomeResolution(
                status="unresolved_outcome_not_yet_available",
                detail=(
                    "No initial vintage is recorded yet; governed expected "
                    f"release date is {expected.isoformat()}, after evaluation "
                    f"as-of {as_of.isoformat()}."
                ),
                release_date=None,
                value=None,
                evidence_source=None,
            )

        expectation = (
            f" Governed expected release date was {expected.isoformat()}."
            if expected is not None
            else ""
        )
        return OutcomeResolution(
            status="unresolved_initial_vintage_not_ingested",
            detail=(
                "Target period is complete but no explicit initial-vintage "
                "observation is locally recorded. Phase 3B refuses to "
                "substitute a latest/revised value."
                + expectation
            ),
            release_date=None,
            value=None,
            evidence_source=None,
        )

    if release_date > as_of:
        return OutcomeResolution(
            status="unresolved_outcome_not_yet_available",
            detail=(
                f"Recorded initial release is dated {release_date.isoformat()}, "
                f"after evaluation as-of {as_of.isoformat()}."
            ),
            release_date=release_date,
            value=None,
            evidence_source="observations.initial",
        )

    snapshot = repository.historical_snapshot(
        release_date,
        [target.series_id],
    )
    if snapshot.empty:
        return OutcomeResolution(
            status="unresolved_release_snapshot_not_cached",
            detail=(
                "Initial release date is known, but the exact ALFRED/FRED "
                "release-date snapshot is not cached locally. Phase 3B "
                "refuses to substitute independently stored initial levels "
                "or a latest/revised value."
            ),
            release_date=release_date,
            value=None,
            evidence_source="observations.initial_release_date",
        )

    try:
        actual = _actual_from_release_snapshot(
            snapshot,
            target=target,
            target_period=period,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return OutcomeResolution(
            status="unresolved_outcome_transform_error",
            detail=str(exc),
            release_date=release_date,
            value=None,
            evidence_source="historical_snapshots.release_date",
        )

    return OutcomeResolution(
        status="resolved",
        detail=(
            "Resolved from the exact cached release-date historical snapshot. "
            "The release date was identified from explicit initial-vintage "
            "metadata; no current/latest value was substituted."
        ),
        release_date=release_date,
        value=actual,
        evidence_source="historical_snapshots.release_date",
    )


def _forecast_identity(row: pd.Series) -> str:
    natural_key = "|".join(
        [
            str(row["model_id"]),
            str(row["model_version"]),
            str(row["run_id"]),
            str(row["target_series"]),
            str(row["target_period"]),
        ]
    )
    return _sha256_text(natural_key)


def _evaluate_row(
    row: pd.Series,
    *,
    resolution: OutcomeResolution,
    as_of: date,
) -> dict[str, Any]:
    cutoff = _to_date(row.get("information_cutoff"))
    forecast_value = _to_float(row.get("forecast_value"))
    lower = _to_float(row.get("lower_80"))
    upper = _to_float(row.get("upper_80"))
    release_date = resolution.release_date

    no_look_ahead: bool | None
    lead_days: int | None
    if cutoff is None or release_date is None:
        no_look_ahead = None
        lead_days = None
    else:
        lead_days = int((release_date - cutoff).days)
        # Date-only timestamps cannot establish ordering within the same day.
        # Fail closed: a valid forecast must precede the initial-release date.
        no_look_ahead = bool(cutoff < release_date)

    status = resolution.status
    detail = resolution.detail
    outcome_value = resolution.value

    if cutoff is None:
        status = "invalid_missing_information_cutoff"
        detail = "Governed forecast row has no information cutoff."
    elif forecast_value is None:
        status = "invalid_missing_forecast_value"
        detail = "Governed forecast row has no finite production forecast."
    elif release_date is not None and no_look_ahead is False:
        status = "invalid_no_look_ahead"
        detail = (
            "Forecast information cutoff is on or after the recorded "
            "initial-release date; Phase 3B refuses to score it."
        )
        outcome_value = None

    signed_error: float | None = None
    absolute_error: float | None = None
    squared_error: float | None = None
    interval_covered: bool | None = None
    if status == "resolved" and forecast_value is not None and outcome_value is not None:
        # Canonical Phase III convention: positive signed error means overprediction.
        signed_error = float(forecast_value - outcome_value)
        absolute_error = float(abs(signed_error))
        squared_error = float(signed_error**2)
        if lower is not None and upper is not None:
            interval_covered = bool(lower <= outcome_value <= upper)

    interval_width = (
        float(upper - lower)
        if lower is not None and upper is not None
        else None
    )

    forecast_identity = _forecast_identity(row)
    evaluation_id = _sha256_text(
        "|".join(
            [
                forecast_identity,
                OUTCOME_VINTAGE,
                as_of.isoformat(),
            ]
        )
    )

    return {
        "evaluation_id": evaluation_id,
        "forecast_identity": forecast_identity,
        "evaluation_as_of": as_of,
        "component": str(row["component"]),
        "model_id": str(row["model_id"]),
        "model_version": str(row["model_version"]),
        "run_id": str(row["run_id"]),
        "information_cutoff": cutoff,
        "data_as_of": _to_date(row.get("data_as_of")),
        "target_series": str(row["target_series"]),
        "target_name": str(row["target_name"]),
        "target_period": str(row["target_period"]),
        "forecast_stage": (
            None
            if row.get("forecast_stage") is None or pd.isna(row.get("forecast_stage"))
            else str(row.get("forecast_stage"))
        ),
        "forecast_model_name": (
            None
            if row.get("forecast_model_name") is None
            or pd.isna(row.get("forecast_model_name"))
            else str(row.get("forecast_model_name"))
        ),
        "forecast_value": forecast_value,
        "lower_80": lower,
        "upper_80": upper,
        "interval_width": interval_width,
        "estimated_release_date": _to_date(row.get("estimated_release_date")),
        "outcome_definition": OUTCOME_DEFINITION,
        "outcome_vintage": OUTCOME_VINTAGE,
        "outcome_evidence_source": resolution.evidence_source,
        "outcome_release_date": release_date,
        "outcome_value": outcome_value,
        "evaluation_status": status,
        "status_detail": detail,
        "no_look_ahead_pass": no_look_ahead,
        "lead_days": lead_days,
        "signed_error": signed_error,
        "absolute_error": absolute_error,
        "squared_error": squared_error,
        "interval_covered": interval_covered,
    }


def build_forecast_evaluation_ledger(
    repository: MacroRepository,
    *,
    as_of: date,
    project_root: Path,
) -> pd.DataFrame:
    if as_of > date.today():
        raise ValueError("Evaluation as-of date cannot be in the future.")

    forecasts = collect_governed_forecasts(
        repository,
        as_of=as_of,
        project_root=project_root,
    )
    if forecasts.empty:
        return pd.DataFrame(columns=EVALUATION_COLUMNS)

    targets = target_specs()
    outcome_cache: dict[
        tuple[str, str, str, str | None],
        OutcomeResolution,
    ] = {}
    rows: list[dict[str, Any]] = []

    for forecast in forecasts.itertuples(index=False):
        series = str(forecast.target_series)
        component = str(forecast.component)
        key = (component, series)
        target = targets.get(key)
        if target is None:
            raise ValueError(
                f"Governed forecast target is outside Phase III contract: "
                f"{component}/{series}"
            )

        period = str(forecast.target_period)
        expected_release_date = _to_date(forecast.estimated_release_date)
        outcome_key = (
            component,
            series,
            period,
            expected_release_date.isoformat()
            if expected_release_date is not None
            else None,
        )
        if outcome_key not in outcome_cache:
            outcome_cache[outcome_key] = resolve_first_release_outcome(
                repository,
                target=target,
                target_period=period,
                as_of=as_of,
                expected_release_date=expected_release_date,
            )

        row_series = pd.Series(forecast._asdict())
        rows.append(
            _evaluate_row(
                row_series,
                resolution=outcome_cache[outcome_key],
                as_of=as_of,
            )
        )

    ledger = pd.DataFrame(rows, columns=EVALUATION_COLUMNS)
    return ledger.sort_values(
        [
            "component",
            "information_cutoff",
            "target_series",
            "target_period",
            "run_id",
        ],
        kind="stable",
    ).reset_index(drop=True)


def _status_bucket(status: str) -> str:
    if status == "resolved":
        return "resolved"
    if status == "structurally_unavailable":
        return "structural"
    if status.startswith("invalid_"):
        return "invalid"
    return "unresolved"


def summarise_forecast_evaluation(
    ledger: pd.DataFrame,
    *,
    as_of: date,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "as_of": as_of,
        "outcome_vintage": OUTCOME_VINTAGE,
        "outcome_definition": OUTCOME_DEFINITION,
        "signed_error_convention": SIGNED_ERROR_CONVENTION,
        "forecast_rows": int(len(ledger)),
        "resolved_rows": 0,
        "unresolved_rows": 0,
        "structurally_unavailable_rows": 0,
        "invalid_rows": 0,
        "components": {},
    }
    if ledger.empty:
        return summary

    buckets = ledger["evaluation_status"].astype(str).map(_status_bucket)
    summary["resolved_rows"] = int((buckets == "resolved").sum())
    summary["unresolved_rows"] = int((buckets == "unresolved").sum())
    summary["structurally_unavailable_rows"] = int(
        (buckets == "structural").sum()
    )
    summary["invalid_rows"] = int((buckets == "invalid").sum())

    for component in PRODUCTION_COMPONENTS:
        part = ledger.loc[ledger["component"] == component]
        part_buckets = part["evaluation_status"].astype(str).map(_status_bucket)
        summary["components"][component] = {
            "forecast_rows": int(len(part)),
            "resolved_rows": int((part_buckets == "resolved").sum()),
            "unresolved_rows": int((part_buckets == "unresolved").sum()),
            "structurally_unavailable_rows": int(
                (part_buckets == "structural").sum()
            ),
            "invalid_rows": int((part_buckets == "invalid").sum()),
        }
    return summary


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


def serialise_forecast_evaluation(
    ledger: pd.DataFrame,
    *,
    as_of: date,
) -> dict[str, Any]:
    summary = summarise_forecast_evaluation(ledger, as_of=as_of)
    serialised_summary = {
        key: (
            {
                sub_key: _json_value(sub_value)
                for sub_key, sub_value in value.items()
            }
            if isinstance(value, dict)
            and key == "components"
            else _json_value(value)
        )
        for key, value in summary.items()
    }
    if "components" in summary:
        serialised_summary["components"] = {
            component: {
                key: _json_value(value)
                for key, value in values.items()
            }
            for component, values in summary["components"].items()
        }

    rows: list[dict[str, Any]] = []
    for record in ledger.to_dict(orient="records"):
        rows.append(
            {key: _json_value(value) for key, value in record.items()}
        )
    return {
        "schema_version": "1.0.0",
        "summary": serialised_summary,
        "ledger": rows,
    }
