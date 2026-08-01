from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.engine import (
    GDP_TARGET,
    INFLATION_TARGETS,
    LABOUR_TARGETS,
    build_dimensions,
    classify_regime,
)
from macropulse.macro_state.history import month_end_dates
from macropulse.settings import settings


TARGET_NAMES = {
    GDP_TARGET: "Real GDP growth",
    "CPIAUCSL": "Headline CPI",
    "CPILFESL": "Core CPI",
    "PCEPI": "Headline PCE Price Index",
    "PCEPILFE": "Core PCE Price Index",
    "PAYEMS": "Nonfarm Payroll Change",
    "UNRATE": "Unemployment Rate",
    "CES0500000003": "Average Hourly Earnings Growth",
}


@dataclass(frozen=True)
class ProductionVintageLineage:
    gdp_validation_id: str
    gdp_backtest_id: str
    inflation_validation_id: str
    inflation_backtest_id: str
    labour_validation_id: str
    labour_backtest_id: str
    gdp_model_version: str
    inflation_model_version: str
    labour_model_version: str

    def as_dict(self) -> dict[str, str]:
        return {
            "gdp_validation_id": self.gdp_validation_id,
            "gdp_backtest_id": self.gdp_backtest_id,
            "inflation_validation_id": self.inflation_validation_id,
            "inflation_backtest_id": self.inflation_backtest_id,
            "labour_validation_id": self.labour_validation_id,
            "labour_backtest_id": self.labour_backtest_id,
            "gdp_model_version": self.gdp_model_version,
            "inflation_model_version": self.inflation_model_version,
            "labour_model_version": self.labour_model_version,
        }


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _hash(value: Any) -> str:
    return hashlib.sha256(
        _canonical_json(value).encode("utf-8")
    ).hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML mapping in {path}.")
    return payload


def _governance_files() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = settings.project_root
    return (
        _load_yaml(root / "config" / "model_governance.yml"),
        _load_yaml(root / "config" / "inflation_governance.yml"),
        _load_yaml(root / "config" / "labour_governance.yml"),
    )


def resolve_production_vintage_lineage(
    repository: MacroRepository,
) -> tuple[ProductionVintageLineage, dict[str, Any]]:
    gdp_cfg, inflation_cfg, labour_cfg = _governance_files()

    gdp_validation_id = str(
        gdp_cfg["model"]["approval"]["validation_id"]
    )
    gdp_validation = repository.query_df(
        """
        SELECT stage_backtest_id, model_version, status
        FROM validation_runs
        WHERE validation_id = ?
        LIMIT 1
        """,
        [gdp_validation_id],
    )
    if gdp_validation.empty:
        raise RuntimeError(
            f"Approved Model 1A validation {gdp_validation_id} is not present."
        )
    if str(gdp_validation.iloc[0]["status"]) != "pass":
        raise RuntimeError(
            f"Approved Model 1A validation is not passing: "
            f"{gdp_validation.iloc[0]['status']}"
        )
    gdp_backtest_id = str(gdp_validation.iloc[0]["stage_backtest_id"])

    inflation_validation_id = str(
        inflation_cfg["model"]["approval"]["candidate_validation_id"]
    )
    inflation_validation = repository.query_df(
        """
        SELECT backtest_id, model_version, status
        FROM inflation_validation_runs
        WHERE validation_id = ?
        LIMIT 1
        """,
        [inflation_validation_id],
    )
    if inflation_validation.empty:
        raise RuntimeError(
            "Approved Model 1B candidate validation is not present: "
            f"{inflation_validation_id}"
        )
    if str(inflation_validation.iloc[0]["status"]) != "pass":
        raise RuntimeError(
            f"Approved Model 1B validation is not passing: "
            f"{inflation_validation.iloc[0]['status']}"
        )
    inflation_backtest_id = str(
        inflation_validation.iloc[0]["backtest_id"]
    )

    labour_validation_id = str(
        labour_cfg["model"]["approval"]["candidate_validation_id"]
    )
    labour_validation = repository.query_df(
        """
        SELECT backtest_id, model_version, status
        FROM labour_validation_runs
        WHERE validation_id = ?
        LIMIT 1
        """,
        [labour_validation_id],
    )
    if labour_validation.empty:
        raise RuntimeError(
            "Approved Model 1C candidate validation is not present: "
            f"{labour_validation_id}"
        )
    if str(labour_validation.iloc[0]["status"]) != "pass":
        raise RuntimeError(
            f"Approved Model 1C validation is not passing: "
            f"{labour_validation.iloc[0]['status']}"
        )
    labour_backtest_id = str(labour_validation.iloc[0]["backtest_id"])

    lineage = ProductionVintageLineage(
        gdp_validation_id=gdp_validation_id,
        gdp_backtest_id=gdp_backtest_id,
        inflation_validation_id=inflation_validation_id,
        inflation_backtest_id=inflation_backtest_id,
        labour_validation_id=labour_validation_id,
        labour_backtest_id=labour_backtest_id,
        gdp_model_version=str(gdp_validation.iloc[0]["model_version"]),
        inflation_model_version=str(
            inflation_validation.iloc[0]["model_version"]
        ),
        labour_model_version=str(
            labour_validation.iloc[0]["model_version"]
        ),
    )
    policies = {
        "GDP": gdp_cfg["production_policy"]["stable_stage_policy"],
        "inflation": inflation_cfg["policy_candidate"]["stable_map"],
        "labour": labour_cfg["policy_candidate"]["stable_map"],
        "inflation_interval_method": inflation_cfg["interval_candidate"]["method"],
        "labour_interval_method": labour_cfg["interval_candidate"]["method"],
    }
    return lineage, policies


def gdp_stage_for_month(state_date: date) -> str:
    month_position = ((state_date.month - 1) % 3) + 1
    return {
        1: "early_quarter",
        2: "after_month_1",
        3: "quarter_end",
    }[month_position]


def _latest_calibration_id(
    repository: MacroRepository,
    table: str,
    backtest_id: str,
    method: str,
) -> str | None:
    frame = repository.query_df(
        f"""
        SELECT calibration_id
        FROM {table}
        WHERE backtest_id = ?
          AND method = ?
          AND status = 'success'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [backtest_id, method],
    )
    if frame.empty:
        return None
    return str(frame.iloc[0]["calibration_id"])


def _calibrated_interval(
    repository: MacroRepository,
    result_table: str,
    calibration_id: str | None,
    backtest_id: str,
    target_series: str,
    forecast_stage: str,
    target_period: str,
    model_name: str,
) -> tuple[float | None, float | None, str]:
    if calibration_id is None:
        return None, None, "vintage_backtest"
    frame = repository.query_df(
        f"""
        SELECT lower_80, upper_80, calibration_status
        FROM {result_table}
        WHERE calibration_id = ?
          AND backtest_id = ?
          AND target_series = ?
          AND forecast_stage = ?
          AND target_period = ?
          AND model_name = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [
            calibration_id,
            backtest_id,
            target_series,
            forecast_stage,
            target_period,
            model_name,
        ],
    )
    if frame.empty:
        return None, None, "vintage_backtest"
    row = frame.iloc[0]
    if (
        str(row["calibration_status"]) != "calibrated"
        or pd.isna(row["lower_80"])
        or pd.isna(row["upper_80"])
    ):
        return None, None, "vintage_backtest"
    return (
        float(row["lower_80"]),
        float(row["upper_80"]),
        "approved_prior_only_calibration",
    )


def _gdp_input(
    repository: MacroRepository,
    state_date: date,
    lineage: ProductionVintageLineage,
    policies: dict[str, Any],
) -> dict[str, Any] | None:
    target_period = str(pd.Period(state_date, freq="Q"))
    forecast_stage = gdp_stage_for_month(state_date)
    model_name = str(policies["GDP"][forecast_stage])
    frame = repository.query_df(
        """
        SELECT *
        FROM stage_backtest_results
        WHERE stage_backtest_id = ?
          AND target_period = ?
          AND forecast_stage = ?
          AND model_name = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [
            lineage.gdp_backtest_id,
            target_period,
            forecast_stage,
            model_name,
        ],
    )
    if frame.empty:
        return None
    row = frame.iloc[0]
    forecast_date = pd.Timestamp(row["forecast_date"]).date()
    actual_release = (
        pd.Timestamp(row["actual_release_date"]).date()
        if pd.notna(row["actual_release_date"])
        else None
    )
    if forecast_date > state_date:
        return None
    if actual_release is not None and actual_release <= state_date:
        return None
    if any(
        pd.isna(row[column])
        for column in ("point_forecast", "lower_80", "upper_80")
    ):
        return None
    return {
        "source_model_id": "US_GDP_NOWCAST_1A",
        "source_model_version": lineage.gdp_model_version,
        "source_run_id": lineage.gdp_backtest_id,
        "source_validation_id": lineage.gdp_validation_id,
        "source_target": GDP_TARGET,
        "source_target_name": TARGET_NAMES[GDP_TARGET],
        "target_period": target_period,
        "forecast_stage": forecast_stage,
        "point_forecast": float(row["point_forecast"]),
        "lower_80": float(row["lower_80"]),
        "upper_80": float(row["upper_80"]),
        "information_cutoff": forecast_date,
        "data_as_of": forecast_date,
        "actual_release_date": actual_release,
        "target_leakage": False,
        "max_observation_date": forecast_date,
        "interval_source": str(
            row["interval_method"]
            if pd.notna(row["interval_method"])
            else "stage_backtest_interval"
        ),
        "model_name": model_name,
        "information_set_hash": str(
            row["information_set_hash"]
            if pd.notna(row["information_set_hash"])
            else ""
        ),
    }


def _inflation_inputs(
    repository: MacroRepository,
    state_date: date,
    lineage: ProductionVintageLineage,
    policies: dict[str, Any],
) -> list[dict[str, Any]] | None:
    target_period = str(pd.Period(state_date, freq="M"))
    forecast_stage = "month_end"
    calibration_id = _latest_calibration_id(
        repository,
        "inflation_interval_calibration_runs",
        lineage.inflation_backtest_id,
        str(policies["inflation_interval_method"]),
    )
    rows: list[dict[str, Any]] = []
    for target in INFLATION_TARGETS:
        model_name = str(
            policies["inflation"][target][forecast_stage]
        )
        frame = repository.query_df(
            """
            SELECT *
            FROM inflation_vintage_backtest_results
            WHERE backtest_id = ?
              AND target_series = ?
              AND target_period = ?
              AND forecast_stage = ?
              AND model_name = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [
                lineage.inflation_backtest_id,
                target,
                target_period,
                forecast_stage,
                model_name,
            ],
        )
        if frame.empty:
            return None
        row = frame.iloc[0]
        forecast_date = pd.Timestamp(row["forecast_date"]).date()
        actual_release = (
            pd.Timestamp(row["actual_release_date"]).date()
            if pd.notna(row["actual_release_date"])
            else None
        )
        max_observation = (
            pd.Timestamp(row["max_observation_date"]).date()
            if pd.notna(row["max_observation_date"])
            else None
        )
        leakage = bool(row["target_leakage"])
        if forecast_date > state_date or leakage:
            return None
        if max_observation is not None and max_observation > forecast_date:
            return None
        calibrated_lower, calibrated_upper, interval_source = (
            _calibrated_interval(
                repository,
                "inflation_interval_calibrated_results",
                calibration_id,
                lineage.inflation_backtest_id,
                target,
                forecast_stage,
                target_period,
                model_name,
            )
        )
        lower = (
            calibrated_lower
            if calibrated_lower is not None
            else (
                float(row["lower_80"])
                if pd.notna(row["lower_80"])
                else None
            )
        )
        upper = (
            calibrated_upper
            if calibrated_upper is not None
            else (
                float(row["upper_80"])
                if pd.notna(row["upper_80"])
                else None
            )
        )
        if pd.isna(row["point_forecast"]) or lower is None or upper is None:
            return None
        rows.append(
            {
                "source_model_id": "US_INFLATION_NOWCAST_1B",
                "source_model_version": lineage.inflation_model_version,
                "source_run_id": lineage.inflation_backtest_id,
                "source_validation_id": lineage.inflation_validation_id,
                "source_target": target,
                "source_target_name": TARGET_NAMES[target],
                "target_period": target_period,
                "forecast_stage": forecast_stage,
                "point_forecast": float(row["point_forecast"]),
                "lower_80": float(lower),
                "upper_80": float(upper),
                "information_cutoff": forecast_date,
                "data_as_of": max_observation,
                "actual_release_date": actual_release,
                "target_leakage": leakage,
                "max_observation_date": max_observation,
                "interval_source": interval_source,
                "model_name": model_name,
                "information_set_hash": str(
                    row["information_set_hash"]
                    if pd.notna(row["information_set_hash"])
                    else ""
                ),
            }
        )
    return rows


def _labour_inputs(
    repository: MacroRepository,
    state_date: date,
    lineage: ProductionVintageLineage,
    policies: dict[str, Any],
) -> list[dict[str, Any]] | None:
    target_period = str(pd.Period(state_date, freq="M"))
    forecast_stage = "month_end"
    calibration_id = _latest_calibration_id(
        repository,
        "labour_interval_calibration_runs",
        lineage.labour_backtest_id,
        str(policies["labour_interval_method"]),
    )
    rows: list[dict[str, Any]] = []
    for target in LABOUR_TARGETS:
        model_name = str(
            policies["labour"][target][forecast_stage]
        )
        frame = repository.query_df(
            """
            SELECT *
            FROM labour_vintage_backtest_results
            WHERE backtest_id = ?
              AND target_series = ?
              AND target_period = ?
              AND forecast_stage = ?
              AND model_name = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [
                lineage.labour_backtest_id,
                target,
                target_period,
                forecast_stage,
                model_name,
            ],
        )
        if frame.empty:
            return None
        row = frame.iloc[0]
        forecast_date = pd.Timestamp(row["forecast_date"]).date()
        actual_release = (
            pd.Timestamp(row["actual_release_date"]).date()
            if pd.notna(row["actual_release_date"])
            else None
        )
        max_observation = (
            pd.Timestamp(row["max_observation_date"]).date()
            if pd.notna(row["max_observation_date"])
            else None
        )
        leakage = bool(row["target_leakage"])
        if forecast_date > state_date or leakage:
            return None
        if max_observation is not None and max_observation > forecast_date:
            return None
        calibrated_lower, calibrated_upper, interval_source = (
            _calibrated_interval(
                repository,
                "labour_interval_calibrated_results",
                calibration_id,
                lineage.labour_backtest_id,
                target,
                forecast_stage,
                target_period,
                model_name,
            )
        )
        lower = (
            calibrated_lower
            if calibrated_lower is not None
            else (
                float(row["lower_80"])
                if pd.notna(row["lower_80"])
                else None
            )
        )
        upper = (
            calibrated_upper
            if calibrated_upper is not None
            else (
                float(row["upper_80"])
                if pd.notna(row["upper_80"])
                else None
            )
        )
        if pd.isna(row["point_forecast"]) or lower is None or upper is None:
            return None
        rows.append(
            {
                "source_model_id": "US_LABOUR_NOWCAST_1C",
                "source_model_version": lineage.labour_model_version,
                "source_run_id": lineage.labour_backtest_id,
                "source_validation_id": lineage.labour_validation_id,
                "source_target": target,
                "source_target_name": TARGET_NAMES[target],
                "target_period": target_period,
                "forecast_stage": forecast_stage,
                "point_forecast": float(row["point_forecast"]),
                "lower_80": float(lower),
                "upper_80": float(upper),
                "information_cutoff": forecast_date,
                "data_as_of": max_observation,
                "actual_release_date": actual_release,
                "target_leakage": leakage,
                "max_observation_date": max_observation,
                "interval_source": interval_source,
                "model_name": model_name,
                "information_set_hash": str(
                    row["information_set_hash"]
                    if pd.notna(row["information_set_hash"])
                    else ""
                ),
            }
        )
    return rows


def vintage_source_bundle(
    repository: MacroRepository,
    state_date: date,
    lineage: ProductionVintageLineage,
    policies: dict[str, Any],
) -> pd.DataFrame:
    gdp = _gdp_input(repository, state_date, lineage, policies)
    inflation = _inflation_inputs(
        repository, state_date, lineage, policies
    )
    labour = _labour_inputs(repository, state_date, lineage, policies)
    if gdp is None or inflation is None or labour is None:
        return pd.DataFrame()
    records = [gdp, *inflation, *labour]
    frame = pd.DataFrame(records)
    if len(frame) != 8:
        return pd.DataFrame()
    frame["source_hash"] = [
        _hash(
            {
                "source_model_id": row.source_model_id,
                "source_model_version": row.source_model_version,
                "source_run_id": row.source_run_id,
                "source_validation_id": row.source_validation_id,
                "source_target": row.source_target,
                "target_period": row.target_period,
                "forecast_stage": row.forecast_stage,
                "model_name": row.model_name,
                "point_forecast": row.point_forecast,
                "lower_80": row.lower_80,
                "upper_80": row.upper_80,
                "information_cutoff": row.information_cutoff,
                "data_as_of": row.data_as_of,
                "actual_release_date": row.actual_release_date,
                "target_leakage": row.target_leakage,
                "max_observation_date": row.max_observation_date,
                "interval_source": row.interval_source,
                "information_set_hash": row.information_set_hash,
            }
        )
        for row in frame.itertuples(index=False)
    ]
    return frame


def _possible_regimes(
    growth_lower: float,
    growth_upper: float,
    inflation_lower: float,
    inflation_upper: float,
    labour_lower: float,
    labour_upper: float,
) -> tuple[str, ...]:
    axes = [
        np.linspace(growth_lower, growth_upper, 9),
        np.linspace(inflation_lower, inflation_upper, 9),
        np.linspace(labour_lower, labour_upper, 9),
    ]
    return tuple(
        sorted(
            {
                classify_regime(growth, inflation, labour)[0]
                for growth, inflation, labour in product(*axes)
            }
        )
    )


def reconstruct_production_vintage_history(
    repository: MacroRepository,
    start_date: date,
    end_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame, ProductionVintageLineage]:
    lineage, policies = resolve_production_vintage_lineage(repository)
    state_rows: list[dict[str, Any]] = []
    input_frames: list[pd.DataFrame] = []

    from macropulse.macro_state.versioning import (
        load_macro_state_governance,
    )
    state_config = load_macro_state_governance()

    for state_date in month_end_dates(start_date, end_date):
        inputs = vintage_source_bundle(
            repository, state_date, lineage, policies
        )
        if inputs.empty:
            continue

        dimensions = build_dimensions(inputs, state_config)
        scores = {item.dimension: item for item in dimensions}
        regime = classify_regime(
            scores["growth"].score,
            scores["inflation"].score,
            scores["labour"].score,
        )
        possible = _possible_regimes(
            scores["growth"].lower_score,
            scores["growth"].upper_score,
            scores["inflation"].lower_score,
            scores["inflation"].upper_score,
            scores["labour"].lower_score,
            scores["labour"].upper_score,
        )

        cutoffs = [
            pd.Timestamp(item).date()
            for item in inputs["information_cutoff"]
        ]
        oldest = min(cutoffs)
        newest = max(cutoffs)
        no_look_ahead = bool(
            all(cutoff <= state_date for cutoff in cutoffs)
            and not inputs["target_leakage"].fillna(False).astype(bool).any()
            and all(
                pd.isna(max_date)
                or pd.Timestamp(max_date).date()
                <= pd.Timestamp(cutoff).date()
                for max_date, cutoff in zip(
                    inputs["max_observation_date"],
                    inputs["information_cutoff"],
                )
            )
        )
        bundle_hash = _hash(
            inputs[
                [
                    "source_model_id",
                    "source_model_version",
                    "source_run_id",
                    "source_validation_id",
                    "source_target",
                    "target_period",
                    "forecast_stage",
                    "model_name",
                    "point_forecast",
                    "lower_80",
                    "upper_80",
                    "information_cutoff",
                    "data_as_of",
                    "actual_release_date",
                    "target_leakage",
                    "max_observation_date",
                    "interval_source",
                    "information_set_hash",
                    "source_hash",
                ]
            ].to_dict(orient="records")
        )

        state_rows.append(
            {
                "state_date": state_date,
                "growth_score": scores["growth"].score,
                "inflation_score": scores["inflation"].score,
                "labour_score": scores["labour"].score,
                "growth_lower": scores["growth"].lower_score,
                "growth_upper": scores["growth"].upper_score,
                "inflation_lower": scores["inflation"].lower_score,
                "inflation_upper": scores["inflation"].upper_score,
                "labour_lower": scores["labour"].lower_score,
                "labour_upper": scores["labour"].upper_score,
                "growth_label": scores["growth"].label,
                "inflation_label": scores["inflation"].label,
                "labour_label": scores["labour"].label,
                "primary_regime": regime[0],
                "primary_regime_label": regime[1],
                "primary_regime_strength": regime[2],
                "possible_regimes_json": json.dumps(possible),
                "possible_regime_count": len(possible),
                "source_cutoff_spread_days": int((newest - oldest).days),
                "no_look_ahead_pass": no_look_ahead,
                "source_bundle_hash": bundle_hash,
            }
        )
        month_inputs = inputs.copy()
        month_inputs.insert(0, "state_date", state_date)
        input_frames.append(month_inputs)

    states = pd.DataFrame(state_rows)
    inputs = (
        pd.concat(input_frames, ignore_index=True)
        if input_frames
        else pd.DataFrame()
    )
    return states, inputs, lineage
