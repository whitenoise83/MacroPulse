from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from macropulse.bvar.data import REQUIRED_SERIES, build_complete_quarter_panel
from macropulse.bvar.model import VARIABLES, fit_bvar
from macropulse.bvar.production import (
    PRODUCTION_HORIZONS,
    run_model2_forecast,
    selected_candidate,
)
from macropulse.bvar.scenario import run_path_scenario
from macropulse.data.repository import MacroRepository


ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "MODEL2_RELEASE.json"

VARIABLE_LABELS = {
    "real_gdp_growth": "Real GDP growth",
    "core_pce_inflation": "Core PCE inflation",
    "unemployment_rate": "Unemployment rate",
    "policy_rate": "Federal funds rate",
}


def _release_metadata() -> dict:
    data = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    if data.get("release_tag") != "model2-bvar-v1.0.2":
        raise RuntimeError("Unexpected Model 2 release identity.")
    return data


def _latest_complete_as_of(repository: MacroRepository):
    placeholders = ", ".join(["?"] * len(REQUIRED_SERIES))
    query = f"""
    SELECT MAX(as_of_date) AS as_of_date
    FROM (
        SELECT as_of_date
        FROM snapshot_downloads
        WHERE status = 'success'
          AND series_id IN ({placeholders})
        GROUP BY as_of_date
        HAVING COUNT(DISTINCT series_id) = ?
    )
    """
    frame = repository.query_df(
        query,
        [*REQUIRED_SERIES, len(REQUIRED_SERIES)],
    )
    if frame.empty or pd.isna(frame.iloc[0]["as_of_date"]):
        return None
    return pd.Timestamp(frame.iloc[0]["as_of_date"]).date()


@st.cache_data(show_spinner=False)
def _build_forecast_view(as_of_iso: str) -> dict:
    cutoff = pd.Timestamp(as_of_iso).date()
    repository = MacroRepository()
    snapshot = repository.historical_snapshot(
        as_of_date=cutoff,
        series_ids=list(REQUIRED_SERIES),
    )
    if snapshot.empty:
        raise RuntimeError("Selected Model 2 exact-vintage snapshot is empty.")

    result = run_model2_forecast(snapshot, cutoff)
    return {
        "point": result.point_forecast.copy(),
        "predictive": result.predictive_summary.copy(),
        "irf": result.structural_irf.copy(),
        "fevd": result.structural_fevd.copy(),
        "candidate_id": result.candidate_id,
        "lags": result.lags,
        "shrinkage": result.shrinkage,
        "information_cutoff": str(result.information_cutoff),
        "first_quarter": result.estimation_first_quarter,
        "last_quarter": result.estimation_last_quarter,
        "observations": result.estimation_observations,
        "panel_hash": result.estimation_panel_hash,
        "snapshot_hash": result.source_snapshot_hash,
        "simulations": result.simulations,
        "seed": result.seed,
        "spectral_radius": result.companion_spectral_radius,
        "predictive_draw_hash": result.predictive_draw_hash,
        "output_fingerprint": result.output_fingerprint,
    }


@st.cache_data(show_spinner=False)
def _run_single_constraint_scenario(
    as_of_iso: str,
    variable: str,
    horizon: int,
    value: float,
) -> dict:
    cutoff = pd.Timestamp(as_of_iso).date()
    repository = MacroRepository()
    snapshot = repository.historical_snapshot(
        as_of_date=cutoff,
        series_ids=list(REQUIRED_SERIES),
    )
    panel = build_complete_quarter_panel(snapshot, cutoff)
    posterior = fit_bvar(panel, selected_candidate())
    constraints = pd.DataFrame(
        [{"horizon": int(horizon), "variable": variable, "value": float(value)}]
    )
    result = run_path_scenario(
        panel,
        posterior,
        constraints,
        scenario_name="streamlit_single_constraint",
    )
    return {
        "scenario_id": result.scenario_id,
        "constraints": result.constraints.copy(),
        "baseline": result.baseline_path.copy(),
        "scenario": result.scenario_path.copy(),
        "comparison": result.comparison.copy(),
    }


st.title("Bayesian VAR Forecasts & Scenarios — Model 2")
st.caption(
    "Frozen Model 2 Bayesian VAR release: probabilistic macro forecasts, "
    "recursive-Cholesky structural diagnostics, and deterministic path scenarios."
)
st.info(
    "Read-only presentation layer. This page does not write to the database, "
    "reselect candidates, retune priors, switch models, or modify Models 1–3."
)

try:
    release = _release_metadata()
except Exception as exc:
    st.error(f"Unable to load Model 2 release metadata: {exc}")
    st.stop()

st.success(
    f"Frozen release: `{release['release_tag']}` | "
    f"selected candidate `{release['selected_specification']['candidate_id']}` | "
    f"p={release['selected_specification']['lags']} | "
    f"lambda={release['selected_specification']['shrinkage']}"
)

repository = MacroRepository()
if not repository.database_path.exists():
    st.error(
        "Local MacroPulse database not found. Expected: "
        f"`{repository.database_path}`"
    )
    st.stop()

try:
    as_of_date = _latest_complete_as_of(repository)
except Exception as exc:
    st.error(f"Unable to resolve latest complete Model 2 information set: {exc}")
    st.stop()

if as_of_date is None:
    st.error(
        "No complete exact-vintage Model 2 snapshot is available for "
        + ", ".join(REQUIRED_SERIES)
        + "."
    )
    st.stop()

st.caption(
    f"Latest complete information cutoff: **{as_of_date.isoformat()}** | "
    "required series: " + ", ".join(REQUIRED_SERIES)
)

with st.spinner("Running frozen Model 2 production forecast..."):
    try:
        view = _build_forecast_view(as_of_date.isoformat())
    except Exception as exc:
        st.error(f"Unable to build Model 2 forecast view: {exc}")
        st.stop()

tabs = st.tabs(
    [
        "Forecasts",
        "Predictive distributions",
        "IRF",
        "FEVD",
        "Scenarios",
        "Provenance",
    ]
)

with tabs[0]:
    st.subheader("Posterior-mean macro forecasts")
    point = view["point"].copy()
    display = point.rename(
        columns={
            "horizon": "Horizon",
            "target_quarter": "Target quarter",
            "real_gdp_growth": "Real GDP growth %",
            "core_pce_inflation": "Core PCE inflation %",
            "unemployment_rate": "Unemployment %",
            "policy_rate": "Federal funds rate %",
        }
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

    for variable in VARIABLES:
        chart = point[["target_quarter", variable]].set_index("target_quarter")
        st.markdown(f"#### {VARIABLE_LABELS[variable]}")
        st.line_chart(chart)

with tabs[1]:
    st.subheader("Posterior predictive distributions")
    pred = view["predictive"].copy()
    variable = st.selectbox(
        "Forecast variable",
        list(VARIABLES),
        format_func=lambda x: VARIABLE_LABELS[x],
        key="model2_predictive_variable",
    )
    selected = pred.loc[pred["variable"].eq(variable)].copy()
    st.dataframe(
        selected[
            [
                "horizon",
                "target_quarter",
                "median",
                "mean",
                "std",
                "lower_50",
                "upper_50",
                "lower_80",
                "upper_80",
                "lower_95",
                "upper_95",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )
    chart = selected.set_index("target_quarter")[
        ["median", "lower_80", "upper_80"]
    ]
    st.line_chart(chart)
    st.caption(
        "Intervals are unconditional posterior predictive intervals from the "
        "frozen Model 2 specification."
    )

with tabs[2]:
    st.subheader("Impulse-response functions")
    st.caption(
        "Identification: recursive Cholesky. Ordering: "
        + " → ".join(release["structural_identification"]["ordering"])
        + ". These are model-based structural diagnostics under the frozen ordering."
    )
    irf = view["irf"].copy()
    response = st.selectbox(
        "Response variable",
        list(VARIABLES),
        format_func=lambda x: VARIABLE_LABELS[x],
        key="model2_irf_response",
    )
    shock = st.selectbox(
        "Shock variable",
        list(VARIABLES),
        format_func=lambda x: VARIABLE_LABELS[x],
        key="model2_irf_shock",
    )
    irf_selected = irf.loc[
        irf["response"].eq(response) & irf["shock"].eq(shock)
    ].copy()
    st.dataframe(irf_selected, use_container_width=True, hide_index=True)
    if not irf_selected.empty:
        st.line_chart(irf_selected.set_index("horizon")[["response_value"]])

with tabs[3]:
    st.subheader("Forecast-error variance decomposition")
    fevd = view["fevd"].copy()
    response = st.selectbox(
        "FEVD response variable",
        list(VARIABLES),
        format_func=lambda x: VARIABLE_LABELS[x],
        key="model2_fevd_response",
    )
    subset = fevd.loc[fevd["response"].eq(response)].copy()
    st.dataframe(subset, use_container_width=True, hide_index=True)
    if {"horizon", "shock", "share"}.issubset(subset.columns):
        pivot = subset.pivot(index="horizon", columns="shock", values="share")
        st.line_chart(pivot)

with tabs[4]:
    st.subheader("Deterministic conditional path scenario")
    st.warning(
        "Scenario conditioning is mechanical, not a Bayesian conditional density, "
        "not a probability statement, and not an independent causal claim."
    )
    variable = st.selectbox(
        "Constrained variable",
        list(VARIABLES),
        format_func=lambda x: VARIABLE_LABELS[x],
        key="model2_scenario_variable",
    )
    horizon = st.selectbox(
        "Constraint horizon (quarters ahead)",
        list(range(1, 9)),
        key="model2_scenario_horizon",
    )

    point = view["point"]
    if int(horizon) in set(point["horizon"]):
        baseline_default = float(
            point.loc[point["horizon"].eq(int(horizon)), variable].iloc[0]
        )
    else:
        baseline_default = 0.0

    value = st.number_input(
        "Constraint value",
        value=baseline_default,
        step=0.25,
        format="%.3f",
        key="model2_scenario_value",
    )

    if st.button("Run path scenario", type="primary"):
        with st.spinner("Running frozen Model 2 deterministic scenario..."):
            try:
                scenario = _run_single_constraint_scenario(
                    as_of_date.isoformat(),
                    variable,
                    int(horizon),
                    float(value),
                )
            except Exception as exc:
                st.error(f"Scenario failed: {exc}")
            else:
                st.caption(f"Scenario ID: `{scenario['scenario_id']}`")
                comparison = scenario["comparison"].copy()
                st.dataframe(
                    comparison,
                    use_container_width=True,
                    hide_index=True,
                )
                variable_comparison = comparison.loc[
                    comparison["variable"].eq(variable)
                ].copy()
                if not variable_comparison.empty:
                    chart = variable_comparison.set_index("target_quarter")[
                        ["baseline_value", "scenario_value"]
                    ]
                    st.line_chart(chart)

with tabs[5]:
    st.subheader("Production provenance")
    cols = st.columns(4)
    cols[0].metric("Estimation origin", view["last_quarter"])
    cols[1].metric("Observations", view["observations"])
    cols[2].metric("Simulations", view["simulations"])
    cols[3].metric("Spectral radius", f"{view['spectral_radius']:.4f}")

    st.write(
        f"Release: `{release['release_tag']}`  \n"
        f"Candidate: `{view['candidate_id']}`  \n"
        f"Estimation sample: `{view['first_quarter']}` to `{view['last_quarter']}`  \n"
        f"Information cutoff: `{view['information_cutoff']}`  \n"
        f"Panel hash: `{view['panel_hash']}`  \n"
        f"Snapshot hash: `{view['snapshot_hash']}`  \n"
        f"Simulation seed: `{view['seed']}`  \n"
        f"Predictive draw hash: `{view['predictive_draw_hash']}`  \n"
        f"Output fingerprint: `{view['output_fingerprint']}`"
    )
    st.caption(
        "Model 2 v1.0.2 is a release-engineering patch over unchanged frozen "
        "forecast semantics and selected specification."
    )
