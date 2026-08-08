from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from macropulse.data.repository import MacroRepository


MODEL_ORDER = ("1A", "1B", "1C", "1D")
PRODUCTION_COMPONENTS = ("1A", "1B", "1C")

# Platform-health thresholds only. These do not change any model specification.
FREQUENCY_STALE_DAYS = {
    "D": 10,
    "DAILY": 10,
    "W": 21,
    "WEEKLY": 21,
    "M": 75,
    "MONTHLY": 75,
    "Q": 180,
    "QUARTERLY": 180,
}
UNKNOWN_FREQUENCY_STALE_DAYS = 90
UPCOMING_RELEASE_HORIZON_DAYS = 14


@dataclass(frozen=True)
class ComponentSpec:
    key: str
    model_id: str
    model_version: str
    lifecycle_status: str
    run_table: str
    information_set_table: str | None


def load_phase2_boundary(project_root: Path) -> dict[str, Any]:
    path = project_root / "PHASE2_BOUNDARY.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("phase") != "II":
        raise ValueError("PHASE2_BOUNDARY.json must declare Phase II.")
    suite = payload.get("model_suite")
    if not isinstance(suite, dict):
        raise ValueError("PHASE2_BOUNDARY.json must contain model_suite.")
    return payload


def component_specs(project_root: Path) -> dict[str, ComponentSpec]:
    boundary = load_phase2_boundary(project_root)
    suite = boundary["model_suite"]

    expected = {
        "1A": ("US_GDP_NOWCAST_1A", "forecast_registry", "nowcast_information_sets"),
        "1B": ("US_INFLATION_NOWCAST_1B", "inflation_live_runs", "inflation_live_information_sets"),
        "1C": ("US_LABOUR_NOWCAST_1C", "labour_live_runs", "labour_live_information_sets"),
        "1D": ("US_MACRO_STATE_1D", "macro_state_shadow_runs", None),
    }
    specs: dict[str, ComponentSpec] = {}
    for key in MODEL_ORDER:
        item = suite[key]
        model_id, run_table, info_table = expected[key]
        specs[key] = ComponentSpec(
            key=key,
            model_id=model_id,
            model_version=str(item["version"]),
            lifecycle_status=str(item["status"]),
            run_table=run_table,
            information_set_table=info_table,
        )
    return specs


def _to_date(value: Any) -> date | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date()


def _normalise_frequency(value: Any) -> str:
    if value is None or pd.isna(value):
        return "UNKNOWN"

    text = str(value).strip().upper()
    exact = {
        "D": "D",
        "W": "W",
        "M": "M",
        "Q": "Q",
    }
    if text in exact:
        return exact[text]

    prefixes = (
        ("DAILY", "D"),
        ("WEEKLY", "W"),
        ("MONTHLY", "M"),
        ("QUARTERLY", "Q"),
    )
    for prefix, canonical in prefixes:
        if text.startswith(prefix):
            return canonical

    return "UNKNOWN"


def freshness_threshold_days(frequency: Any) -> int:
    normalised = _normalise_frequency(frequency)
    return int(FREQUENCY_STALE_DAYS.get(normalised, UNKNOWN_FREQUENCY_STALE_DAYS))


def classify_source_freshness(
    *,
    latest_observation_date: date | None,
    frequency: Any,
    as_of: date,
    release_due: bool,
) -> dict[str, Any]:
    normalised = _normalise_frequency(frequency)
    threshold = freshness_threshold_days(normalised)
    if latest_observation_date is None:
        return {
            "freshness_state": "missing_observation",
            "age_days": None,
            "threshold_days": threshold,
            "stale": True,
            "frequency": normalised,
        }

    age_days = int((as_of - latest_observation_date).days)
    stale_by_age = age_days > threshold
    if release_due:
        state = "stale_release_due"
    elif stale_by_age:
        state = "stale_age"
    elif normalised == "UNKNOWN":
        state = "indeterminate_frequency"
    else:
        state = "fresh"

    return {
        "freshness_state": state,
        "age_days": age_days,
        "threshold_days": threshold,
        "stale": bool(release_due or stale_by_age or normalised == "UNKNOWN"),
        "frequency": normalised,
    }


def _latest_run(
    repository: MacroRepository,
    *,
    spec: ComponentSpec,
    as_of: date,
) -> pd.DataFrame:
    if spec.key == "1A":
        return repository.query_df(
            """
            SELECT run_id, model_id, model_version, information_cutoff,
                   data_as_of, target_period, forecast_stage, status, created_at
            FROM forecast_registry
            WHERE model_id = ?
              AND model_version = ?
              AND status = 'success'
              AND information_cutoff <= ?
            ORDER BY information_cutoff DESC, created_at DESC
            LIMIT 1
            """,
            [spec.model_id, spec.model_version, as_of],
        )

    if spec.key in {"1B", "1C"}:
        return repository.query_df(
            f"""
            SELECT run_id, model_id, model_version, run_timestamp,
                   information_cutoff, data_as_of, status
            FROM {spec.run_table}
            WHERE model_id = ?
              AND model_version = ?
              AND status = 'success'
              AND information_cutoff <= ?
            ORDER BY information_cutoff DESC, run_timestamp DESC
            LIMIT 1
            """,
            [spec.model_id, spec.model_version, as_of],
        )

    return repository.query_df(
        """
        SELECT shadow_run_id, model_id, model_version, run_timestamp,
               state_date, information_cutoff, target_expected_available_date,
               gdp_run_id, inflation_run_id, labour_run_id,
               no_look_ahead_pass, status, created_at
        FROM macro_state_shadow_runs
        WHERE model_id = ?
          AND model_version = ?
          AND information_cutoff <= ?
        ORDER BY state_date DESC, created_at DESC
        LIMIT 1
        """,
        [spec.model_id, spec.model_version, as_of],
    )


def _information_set(
    repository: MacroRepository,
    *,
    table: str,
    run_id: str,
) -> pd.DataFrame:
    return repository.query_df(
        f"""
        SELECT series_id, observation_date
        FROM {table}
        WHERE run_id = ?
        ORDER BY series_id, observation_date
        """,
        [run_id],
    )


def _series_metadata(
    repository: MacroRepository,
    series_ids: Iterable[str],
) -> pd.DataFrame:
    values = sorted({str(value) for value in series_ids if str(value)})
    if not values:
        return pd.DataFrame(columns=["series_id", "frequency"])
    placeholders = ", ".join(["?"] * len(values))
    return repository.query_df(
        f"""
        SELECT series_id, frequency
        FROM series_metadata
        WHERE series_id IN ({placeholders})
        ORDER BY series_id
        """,
        values,
    )


def _release_calendar(
    repository: MacroRepository,
    *,
    series_ids: Iterable[str],
    start_exclusive: date,
    end_inclusive: date,
) -> pd.DataFrame:
    values = sorted({str(value) for value in series_ids if str(value)})
    columns = ["series_id", "release_id", "release_name", "release_date"]
    if not values:
        return pd.DataFrame(columns=columns)
    placeholders = ", ".join(["?"] * len(values))
    return repository.query_df(
        f"""
        SELECT series_id, release_id, release_name, release_date
        FROM release_calendar
        WHERE series_id IN ({placeholders})
          AND release_date > ?
          AND release_date <= ?
        ORDER BY release_date, series_id, release_id
        """,
        [*values, start_exclusive, end_inclusive],
    )


def build_source_health(
    information_set: pd.DataFrame,
    metadata: pd.DataFrame,
    due_releases: pd.DataFrame,
    *,
    component: str,
    run_id: str,
    information_cutoff: date,
    as_of: date,
) -> pd.DataFrame:
    columns = [
        "component",
        "run_id",
        "series_id",
        "frequency",
        "latest_observation_date",
        "age_days",
        "threshold_days",
        "release_due_since_run",
        "freshness_state",
        "stale",
    ]
    if information_set.empty:
        return pd.DataFrame(columns=columns)

    info = information_set.copy()
    info["observation_date"] = pd.to_datetime(
        info["observation_date"], errors="coerce"
    )
    latest = (
        info.groupby("series_id", as_index=False)["observation_date"]
        .max()
        .rename(columns={"observation_date": "latest_observation_date"})
    )

    meta = metadata[["series_id", "frequency"]].copy() if not metadata.empty else pd.DataFrame(
        columns=["series_id", "frequency"]
    )
    latest = latest.merge(meta, on="series_id", how="left")
    due_series = (
        set(due_releases["series_id"].astype(str))
        if not due_releases.empty
        else set()
    )

    rows: list[dict[str, Any]] = []
    for row in latest.itertuples(index=False):
        latest_date = _to_date(row.latest_observation_date)
        release_due = str(row.series_id) in due_series
        health = classify_source_freshness(
            latest_observation_date=latest_date,
            frequency=getattr(row, "frequency", None),
            as_of=as_of,
            release_due=release_due,
        )
        rows.append(
            {
                "component": component,
                "run_id": run_id,
                "series_id": str(row.series_id),
                "frequency": health["frequency"],
                "latest_observation_date": latest_date,
                "age_days": health["age_days"],
                "threshold_days": health["threshold_days"],
                "release_due_since_run": release_due,
                "freshness_state": health["freshness_state"],
                "stale": health["stale"],
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["component", "series_id"]
    ).reset_index(drop=True)


def _component_summary(
    *,
    spec: ComponentSpec,
    latest_run: pd.DataFrame,
    source_health: pd.DataFrame,
    target_count: int,
    due_release_count: int,
) -> dict[str, Any]:
    if latest_run.empty:
        return {
            "component": spec.key,
            "model_id": spec.model_id,
            "model_version": spec.model_version,
            "lifecycle_status": spec.lifecycle_status,
            "run_id": None,
            "information_cutoff": None,
            "data_as_of": None,
            "target_period": None,
            "forecast_stage": None,
            "target_count": 0,
            "source_series_count": 0,
            "stale_source_count": 0,
            "due_release_count": 0,
            "freshness_state": "missing_run",
            "ready": False,
        }

    row = latest_run.iloc[0]
    run_id = str(row["run_id"])
    source_count = int(source_health["series_id"].nunique()) if not source_health.empty else 0
    stale_count = int(source_health["stale"].astype(bool).sum()) if not source_health.empty else 0

    if source_count == 0:
        freshness = "missing_information_set"
        ready = False
    elif stale_count:
        freshness = "stale"
        ready = False
    else:
        freshness = "fresh"
        ready = True

    return {
        "component": spec.key,
        "model_id": spec.model_id,
        "model_version": spec.model_version,
        "lifecycle_status": spec.lifecycle_status,
        "run_id": run_id,
        "information_cutoff": _to_date(row.get("information_cutoff")),
        "data_as_of": _to_date(row.get("data_as_of")),
        "target_period": row.get("target_period"),
        "forecast_stage": row.get("forecast_stage"),
        "target_count": int(target_count),
        "source_series_count": source_count,
        "stale_source_count": stale_count,
        "due_release_count": int(due_release_count),
        "freshness_state": freshness,
        "ready": bool(ready),
    }


def _target_count(
    repository: MacroRepository,
    *,
    component: str,
    run_id: str,
) -> int:
    if component == "1A":
        return 1
    table = "inflation_live_forecasts" if component == "1B" else "labour_live_forecasts"
    frame = repository.query_df(
        f"SELECT COUNT(*) AS target_count FROM {table} WHERE run_id = ?",
        [run_id],
    )
    if frame.empty:
        return 0
    return int(frame.iloc[0]["target_count"])


def _model1d_summary(
    repository: MacroRepository,
    *,
    spec: ComponentSpec,
    latest_run: pd.DataFrame,
    production_summaries: dict[str, dict[str, Any]],
    as_of: date,
) -> tuple[dict[str, Any], pd.DataFrame]:
    if latest_run.empty:
        summary = {
            "component": "1D",
            "model_id": spec.model_id,
            "model_version": spec.model_version,
            "lifecycle_status": spec.lifecycle_status,
            "run_id": None,
            "information_cutoff": None,
            "data_as_of": None,
            "target_period": None,
            "forecast_stage": None,
            "target_count": 0,
            "source_series_count": 0,
            "stale_source_count": 0,
            "due_release_count": 0,
            "freshness_state": "missing_shadow_run",
            "ready": False,
        }
        detail = pd.DataFrame(
            [
                {
                    "shadow_run_id": None,
                    "state_date": None,
                    "information_cutoff": None,
                    "target_expected_available_date": None,
                    "source_runs_match_latest": False,
                    "source_run_advance_detected": False,
                    "no_look_ahead_pass": False,
                    "outcome_count": 0,
                    "complete_target_months": 0,
                    "shadow_state": "missing_shadow_run",
                }
            ]
        )
        return summary, detail

    row = latest_run.iloc[0]
    shadow_run_id = str(row["shadow_run_id"])
    expected_sources = {
        "gdp_run_id": production_summaries["1A"]["run_id"],
        "inflation_run_id": production_summaries["1B"]["run_id"],
        "labour_run_id": production_summaries["1C"]["run_id"],
    }
    matches = all(
        expected_sources[column] is not None
        and str(row[column]) == str(expected_sources[column])
        for column in expected_sources
    )
    no_look_ahead = bool(row.get("no_look_ahead_pass", False))

    outcomes = repository.query_df(
        """
        SELECT benchmark_id
        FROM macro_state_shadow_outcomes
        WHERE shadow_run_id = ?
          AND CAST(resolved_at AS DATE) <= ?
        ORDER BY benchmark_id
        """,
        [shadow_run_id, as_of],
    )
    outcome_count = int(len(outcomes))

    complete = repository.query_df(
        """
        SELECT COUNT(DISTINCT state_date) AS complete_target_months
        FROM macro_state_shadow_outcomes
        WHERE model_version = ?
          AND benchmark_id = 'source'
          AND CAST(resolved_at AS DATE) <= ?
        """,
        [spec.model_version, as_of],
    )
    complete_months = (
        int(complete.iloc[0]["complete_target_months"])
        if not complete.empty
        else 0
    )

    target_expected = _to_date(row.get("target_expected_available_date"))
    source_run_advance_detected = not matches

    if not no_look_ahead:
        shadow_state = "integrity_error"
    elif target_expected is not None and target_expected <= as_of and outcome_count != 2:
        shadow_state = "due_for_resolution_attempt"
    elif outcome_count == 2:
        shadow_state = "resolved_prospective_observation"
    else:
        shadow_state = "frozen_prospective_observation"

    summary = {
        "component": "1D",
        "model_id": spec.model_id,
        "model_version": spec.model_version,
        "lifecycle_status": spec.lifecycle_status,
        "run_id": shadow_run_id,
        "information_cutoff": _to_date(row.get("information_cutoff")),
        "data_as_of": _to_date(row.get("state_date")),
        "target_period": str(row.get("state_date")),
        "forecast_stage": "prospective_shadow",
        "target_count": 2,
        "source_series_count": 3,
        "stale_source_count": 0,
        "due_release_count": 0,
        "freshness_state": shadow_state,
        "ready": bool(
            no_look_ahead
            and shadow_state
            in {
                "frozen_prospective_observation",
                "resolved_prospective_observation",
            }
        ),
    }
    detail = pd.DataFrame(
        [
            {
                "shadow_run_id": shadow_run_id,
                "state_date": _to_date(row.get("state_date")),
                "information_cutoff": _to_date(row.get("information_cutoff")),
                "target_expected_available_date": target_expected,
                "source_runs_match_latest": bool(matches),
                "source_run_advance_detected": bool(source_run_advance_detected),
                "no_look_ahead_pass": no_look_ahead,
                "outcome_count": outcome_count,
                "complete_target_months": complete_months,
                "shadow_state": shadow_state,
            }
        ]
    )
    return summary, detail


def _upcoming_releases(
    repository: MacroRepository,
    *,
    series_ids: Iterable[str],
    as_of: date,
) -> pd.DataFrame:
    frame = _release_calendar(
        repository,
        series_ids=series_ids,
        start_exclusive=as_of,
        end_inclusive=as_of + timedelta(days=UPCOMING_RELEASE_HORIZON_DAYS),
    )
    if frame.empty:
        return frame
    frame = frame.drop_duplicates(
        subset=["series_id", "release_id", "release_date"]
    ).copy()
    frame["days_until_release"] = pd.to_datetime(frame["release_date"]).map(
        lambda value: (value.date() - as_of).days
    )
    return frame.sort_values(
        ["release_date", "series_id", "release_id"]
    ).reset_index(drop=True)


def _readiness(
    components: pd.DataFrame,
    model1d_detail: pd.DataFrame,
) -> pd.DataFrame:
    production = components.loc[
        components["component"].isin(PRODUCTION_COMPONENTS)
    ].copy()
    source_ready = bool(
        len(production) == len(PRODUCTION_COMPONENTS)
        and production["ready"].astype(bool).all()
    )

    model1d_row = components.loc[components["component"] == "1D"]
    model1d_ready = bool(
        not model1d_row.empty and model1d_row.iloc[0]["ready"]
    )

    blocking = production.loc[~production["ready"].astype(bool), "component"].astype(str).tolist()

    if not source_ready:
        next_action = "refresh_or_repair_production_source_models"
    elif not model1d_ready:
        shadow_state = (
            str(model1d_detail.iloc[0]["shadow_state"])
            if not model1d_detail.empty
            else "missing_shadow_run"
        )
        if shadow_state == "due_for_resolution_attempt":
            next_action = "run_model1d_shadow_operations_for_resolution"
        else:
            next_action = "run_model1d_shadow_operations_when_month_is_eligible"
    else:
        next_action = "no_model_action_required"

    return pd.DataFrame(
        [
            {
                "production_sources_ready": source_ready,
                "model1d_shadow_valid": model1d_ready,
                "platform_ready_for_downstream": source_ready,
                "blocking_components": ",".join(blocking),
                "next_action": next_action,
            }
        ]
    )


def collect_platform_status(
    repository: MacroRepository,
    *,
    as_of: date,
    project_root: Path,
) -> dict[str, Any]:
    specs = component_specs(project_root)
    summaries: dict[str, dict[str, Any]] = {}
    source_health_frames: list[pd.DataFrame] = []
    due_release_frames: list[pd.DataFrame] = []
    all_source_ids: set[str] = set()

    for key in PRODUCTION_COMPONENTS:
        spec = specs[key]
        latest = _latest_run(repository, spec=spec, as_of=as_of)
        if latest.empty:
            summaries[key] = _component_summary(
                spec=spec,
                latest_run=latest,
                source_health=pd.DataFrame(),
                target_count=0,
                due_release_count=0,
            )
            continue

        run_id = str(latest.iloc[0]["run_id"])
        information_cutoff = _to_date(latest.iloc[0]["information_cutoff"])
        if information_cutoff is None:
            summaries[key] = _component_summary(
                spec=spec,
                latest_run=pd.DataFrame(),
                source_health=pd.DataFrame(),
                target_count=0,
                due_release_count=0,
            )
            summaries[key]["freshness_state"] = "missing_information_cutoff"
            continue

        info = _information_set(
            repository,
            table=str(spec.information_set_table),
            run_id=run_id,
        )
        source_ids = set(info["series_id"].astype(str)) if not info.empty else set()
        all_source_ids.update(source_ids)
        metadata = _series_metadata(repository, source_ids)
        due = _release_calendar(
            repository,
            series_ids=source_ids,
            start_exclusive=information_cutoff,
            end_inclusive=as_of,
        )
        if not due.empty:
            due = due.copy()
            due["component"] = key
            due["run_id"] = run_id
            due_release_frames.append(due)

        health = build_source_health(
            info,
            metadata,
            due,
            component=key,
            run_id=run_id,
            information_cutoff=information_cutoff,
            as_of=as_of,
        )
        source_health_frames.append(health)
        target_count = _target_count(repository, component=key, run_id=run_id)
        summaries[key] = _component_summary(
            spec=spec,
            latest_run=latest,
            source_health=health,
            target_count=target_count,
            due_release_count=int(len(due)),
        )

    latest_1d = _latest_run(repository, spec=specs["1D"], as_of=as_of)
    summary_1d, model1d_detail = _model1d_summary(
        repository,
        spec=specs["1D"],
        latest_run=latest_1d,
        production_summaries=summaries,
        as_of=as_of,
    )
    summaries["1D"] = summary_1d

    components = pd.DataFrame(
        [summaries[key] for key in MODEL_ORDER]
    )
    source_health = (
        pd.concat(source_health_frames, ignore_index=True)
        if source_health_frames
        else pd.DataFrame(
            columns=[
                "component", "run_id", "series_id", "frequency",
                "latest_observation_date", "age_days", "threshold_days",
                "release_due_since_run", "freshness_state", "stale",
            ]
        )
    )
    due_releases = (
        pd.concat(due_release_frames, ignore_index=True)
        if due_release_frames
        else pd.DataFrame(
            columns=[
                "series_id", "release_id", "release_name",
                "release_date", "component", "run_id",
            ]
        )
    )
    upcoming = _upcoming_releases(
        repository,
        series_ids=all_source_ids,
        as_of=as_of,
    )
    readiness = _readiness(components, model1d_detail)

    return {
        "as_of": as_of,
        "components": components,
        "source_health": source_health,
        "due_releases": due_releases,
        "upcoming_releases": upcoming,
        "model1d": model1d_detail,
        "readiness": readiness,
    }


def _json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    return value


def serialise_platform_status(result: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {"as_of": str(result["as_of"])}
    for key in (
        "components",
        "source_health",
        "due_releases",
        "upcoming_releases",
        "model1d",
        "readiness",
    ):
        frame = result[key]
        records = frame.where(pd.notna(frame), None).to_dict("records")
        output[key] = [
            {name: _json_value(value) for name, value in record.items()}
            for record in records
        ]
    return output
