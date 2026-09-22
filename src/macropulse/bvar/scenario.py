from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np
import pandas as pd

from macropulse.bvar.model import (
    FORECAST_HORIZONS,
    VARIABLES,
    BVARPosterior,
    _panel_hash,
    _validate_panel,
)


SCENARIO_PATH_HORIZONS = tuple(range(1, 9))
SCENARIO_REPORT_HORIZONS = tuple(FORECAST_HORIZONS)
SCENARIO_LABEL = "scenario"
BASELINE_LABEL = "unconditional_baseline"


@dataclass(frozen=True)
class ScenarioResult:
    candidate_id: str
    scenario_name: str
    scenario_id: str
    estimation_last_quarter: str
    estimation_panel_hash: str
    path_horizons: tuple[int, ...]
    report_horizons: tuple[int, ...]
    constraints: pd.DataFrame
    baseline_path: pd.DataFrame
    scenario_path: pd.DataFrame
    comparison: pd.DataFrame


def _validate_scenario_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Scenario name must be a non-empty string.")
    return name.strip()


def _normalise_constraints(constraints: pd.DataFrame) -> pd.DataFrame:
    required = {"horizon", "variable", "value"}
    missing = sorted(required - set(constraints.columns))
    if missing:
        raise ValueError(
            "Scenario constraints missing required columns: "
            + ", ".join(missing)
        )

    frame = constraints.loc[:, ["horizon", "variable", "value"]].copy()
    if frame.empty:
        raise ValueError("Scenario must contain at least one path constraint.")

    numeric_horizon = pd.to_numeric(frame["horizon"], errors="coerce")
    if numeric_horizon.isna().any():
        raise ValueError("Scenario constraint horizons must be integers.")

    horizon_values = numeric_horizon.to_numpy(dtype=float)
    rounded = np.rint(horizon_values)
    if not np.array_equal(horizon_values, rounded):
        raise ValueError("Scenario constraint horizons must be integers.")

    frame["horizon"] = rounded.astype(int)
    if not frame["horizon"].isin(SCENARIO_PATH_HORIZONS).all():
        raise ValueError(
            "Scenario constraint horizon must be between 1 and 8 quarters."
        )

    frame["variable"] = frame["variable"].astype(str)
    unknown = sorted(set(frame["variable"]) - set(VARIABLES))
    if unknown:
        raise ValueError(
            "Scenario constraint contains unknown variable(s): "
            + ", ".join(unknown)
        )

    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    values = frame["value"].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Scenario constraint values must be finite.")

    duplicates = frame.duplicated(
        subset=["horizon", "variable"],
        keep=False,
    )
    if bool(duplicates.any()):
        raise ValueError(
            "Scenario contains duplicate variable-horizon constraints."
        )

    return frame.sort_values(
        ["horizon", "variable"],
        kind="stable",
    ).reset_index(drop=True)


def _recursive_path(
    frame: pd.DataFrame,
    posterior: BVARPosterior,
    constraints: pd.DataFrame | None,
) -> pd.DataFrame:
    lags = posterior.candidate.lags
    history = [
        row.copy()
        for row in frame.to_numpy(dtype=float)
    ]
    constraint_lookup: dict[tuple[int, str], float] = {}

    if constraints is not None:
        constraint_lookup = {
            (int(row.horizon), str(row.variable)): float(row.value)
            for row in constraints.itertuples(index=False)
        }

    rows: list[dict] = []
    origin = frame.index[-1]

    for horizon in SCENARIO_PATH_HORIZONS:
        design = [1.0]
        for lag in range(1, lags + 1):
            design.extend(history[-lag].tolist())

        future = (
            np.asarray(design, dtype=float)
            @ posterior.posterior_mean
        )
        future = np.asarray(future, dtype=float).copy()

        if not np.isfinite(future).all():
            raise ValueError("Scenario recursion produced non-finite values.")

        for variable_index, variable in enumerate(VARIABLES):
            key = (horizon, variable)
            if key in constraint_lookup:
                future[variable_index] = constraint_lookup[key]

        history.append(future)

        row = {
            "horizon": horizon,
            "target_quarter": str(origin + horizon),
        }
        for variable, value in zip(VARIABLES, future):
            row[variable] = float(value)
        rows.append(row)

    return pd.DataFrame.from_records(rows)


def unconditional_baseline_path(
    panel: pd.DataFrame,
    posterior: BVARPosterior,
) -> pd.DataFrame:
    frame = _validate_panel(panel)
    panel_hash = _panel_hash(frame)

    if panel_hash != posterior.estimation_panel_hash:
        raise ValueError(
            "Scenario panel does not match exact posterior estimation panel."
        )
    if str(frame.index[-1]) != posterior.estimation_last_quarter:
        raise ValueError(
            "Scenario panel last quarter does not match posterior origin."
        )

    return _recursive_path(
        frame,
        posterior,
        constraints=None,
    )


def _scenario_id(
    posterior: BVARPosterior,
    scenario_name: str,
    constraints: pd.DataFrame,
) -> str:
    parts = [
        "model2f",
        f"candidate={posterior.candidate.candidate_id}",
        f"panel={posterior.estimation_panel_hash}",
        f"name={scenario_name}",
    ]
    for row in constraints.itertuples(index=False):
        parts.append(
            f"{int(row.horizon)}|{row.variable}|{float(row.value):.17g}"
        )
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _comparison(
    baseline: pd.DataFrame,
    scenario: pd.DataFrame,
    constraints: pd.DataFrame,
) -> pd.DataFrame:
    constrained_keys = {
        (int(row.horizon), str(row.variable))
        for row in constraints.itertuples(index=False)
    }
    rows: list[dict] = []

    for horizon in SCENARIO_REPORT_HORIZONS:
        baseline_row = baseline.loc[
            baseline["horizon"] == horizon
        ].iloc[0]
        scenario_row = scenario.loc[
            scenario["horizon"] == horizon
        ].iloc[0]

        for variable in VARIABLES:
            baseline_value = float(baseline_row[variable])
            scenario_value = float(scenario_row[variable])
            rows.append(
                {
                    "horizon": horizon,
                    "target_quarter": str(
                        scenario_row["target_quarter"]
                    ),
                    "variable": variable,
                    "baseline_value": baseline_value,
                    "scenario_value": scenario_value,
                    "deviation": scenario_value - baseline_value,
                    "constrained": (
                        horizon,
                        variable,
                    )
                    in constrained_keys,
                }
            )

    return pd.DataFrame.from_records(rows)


def run_path_scenario(
    panel: pd.DataFrame,
    posterior: BVARPosterior,
    constraints: pd.DataFrame,
    *,
    scenario_name: str,
) -> ScenarioResult:
    """
    Run a deterministic hard-path scenario around the unconditional baseline.

    The scenario is a mechanical conditional path, not a Bayesian conditional
    density and not a probability or causal claim. Constrained values replace
    the model-predicted value at that horizon and become part of the state fed
    into later recursive forecasts.
    """
    name = _validate_scenario_name(scenario_name)
    normalised = _normalise_constraints(constraints)

    frame = _validate_panel(panel)
    panel_hash = _panel_hash(frame)
    if panel_hash != posterior.estimation_panel_hash:
        raise ValueError(
            "Scenario panel does not match exact posterior estimation panel."
        )
    if str(frame.index[-1]) != posterior.estimation_last_quarter:
        raise ValueError(
            "Scenario panel last quarter does not match posterior origin."
        )

    baseline = _recursive_path(
        frame,
        posterior,
        constraints=None,
    )
    scenario = _recursive_path(
        frame,
        posterior,
        constraints=normalised,
    )

    return ScenarioResult(
        candidate_id=posterior.candidate.candidate_id,
        scenario_name=name,
        scenario_id=_scenario_id(
            posterior,
            name,
            normalised,
        ),
        estimation_last_quarter=posterior.estimation_last_quarter,
        estimation_panel_hash=panel_hash,
        path_horizons=SCENARIO_PATH_HORIZONS,
        report_horizons=SCENARIO_REPORT_HORIZONS,
        constraints=normalised,
        baseline_path=baseline,
        scenario_path=scenario,
        comparison=_comparison(
            baseline,
            scenario,
            normalised,
        ),
    )
