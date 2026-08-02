from __future__ import annotations

import json
import math
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

GDP_TARGET = "GDPC1"
INFLATION_TARGETS = ("PCEPILFE", "CPILFESL", "PCEPI", "CPIAUCSL")
LABOUR_TARGETS = ("PAYEMS", "UNRATE", "CES0500000003")


Z80 = 1.2815515655446004


def _classify_regime(growth: float, inflation: float, labour: float) -> str:
    g = float(growth)
    i = float(inflation)
    l = float(labour)
    if g <= -0.75 and l <= -0.75:
        return "hard_landing_risk"
    if g <= -0.75 and i >= 0.75:
        return "stagflation_risk"
    if g >= 0.75 and i >= 0.75 and l >= 0.50:
        return "overheating"
    if g >= 0.25 and i <= -0.25 and l >= -0.50:
        return "disinflationary_expansion"
    if -0.25 <= g <= 0.75 and -0.40 <= i <= 0.40 and -0.50 <= l <= 0.75:
        return "balanced_expansion"
    if g >= 0.25 and i >= 0.25:
        return "reflation"
    if g <= -0.25 and i <= 0.25:
        return "demand_slowdown"
    return "mixed_transition"


def effective_coverage_metrics(states: pd.DataFrame) -> dict[str, Any]:
    if states.empty:
        return {
            "effective_start_date": None,
            "effective_end_date": None,
            "effective_months_requested": 0,
            "effective_coverage_ratio": 0.0,
            "gap_months": 0,
        }
    ordered = states.sort_values("state_date")
    start = pd.Timestamp(ordered.iloc[0]["state_date"]).date()
    end = pd.Timestamp(ordered.iloc[-1]["state_date"]).date()
    requested = len(pd.date_range(start=start, end=end, freq="ME"))
    reconstructed = int(
        pd.PeriodIndex(ordered["state_date"], freq="M").nunique()
    )
    return {
        "effective_start_date": start,
        "effective_end_date": end,
        "effective_months_requested": int(requested),
        "effective_coverage_ratio": (
            float(reconstructed / requested) if requested else 0.0
        ),
        "gap_months": int(max(0, requested - reconstructed)),
    }


def missing_month_ends(states: pd.DataFrame) -> list[date]:
    metrics = effective_coverage_metrics(states)
    if metrics["effective_start_date"] is None:
        return []
    expected = {
        item.date()
        for item in pd.date_range(
            metrics["effective_start_date"],
            metrics["effective_end_date"],
            freq="ME",
        )
    }
    observed = {
        pd.Timestamp(item).date() for item in states["state_date"]
    }
    return sorted(expected.difference(observed))


def _available_models(
    repository: Any,
    *,
    table: str,
    id_column: str,
    source_id: str,
    target_period: str,
    forecast_stage: str,
    target: str | None = None,
) -> list[str]:
    target_clause = ""
    params: list[Any] = [source_id, target_period, forecast_stage]
    if target is not None:
        target_clause = " AND target_series = ?"
        params.append(target)
    frame = repository.query_df(
        f"""
        SELECT DISTINCT model_name
        FROM {table}
        WHERE {id_column} = ?
          AND target_period = ?
          AND forecast_stage = ?
          {target_clause}
        ORDER BY model_name
        """,
        params,
    )
    if frame.empty:
        return []
    return frame["model_name"].astype(str).tolist()


def diagnose_month(
    repository: Any,
    state_date: date,
    lineage: Any,
    policies: dict[str, Any],
) -> pd.DataFrame:
    gaps: list[dict[str, Any]] = []

    def add(
        model_id: str,
        target: str,
        target_period: str,
        stage: str,
        expected_model: str,
        reason: str,
        available: list[str],
    ) -> None:
        gaps.append(
            {
                "state_date": state_date,
                "source_model_id": model_id,
                "source_target": target,
                "target_period": target_period,
                "forecast_stage": stage,
                "expected_model": expected_model,
                "reason": reason,
                "available_models": ", ".join(available),
            }
        )

    gdp_period = str(pd.Period(state_date, freq="Q"))
    from macropulse.macro_state.vintage_history import gdp_stage_for_month

    gdp_stage = gdp_stage_for_month(state_date)
    gdp_model = str(policies["GDP"][gdp_stage])
    gdp = repository.query_df(
        """
        SELECT forecast_date, actual_release_date, point_forecast,
               lower_80, upper_80
        FROM stage_backtest_results
        WHERE stage_backtest_id = ?
          AND target_period = ?
          AND forecast_stage = ?
          AND model_name = ?
        LIMIT 1
        """,
        [lineage.gdp_backtest_id, gdp_period, gdp_stage, gdp_model],
    )
    if gdp.empty:
        available = _available_models(
            repository,
            table="stage_backtest_results",
            id_column="stage_backtest_id",
            source_id=lineage.gdp_backtest_id,
            target_period=gdp_period,
            forecast_stage=gdp_stage,
        )
        add(
            "US_GDP_NOWCAST_1A",
            GDP_TARGET,
            gdp_period,
            gdp_stage,
            gdp_model,
            "stable_model_absent" if available else "target_stage_absent",
            available,
        )
    else:
        row = gdp.iloc[0]
        forecast_date = pd.Timestamp(row["forecast_date"]).date()
        actual_release = (
            pd.Timestamp(row["actual_release_date"]).date()
            if pd.notna(row["actual_release_date"])
            else None
        )
        reason = None
        if forecast_date > state_date:
            reason = "forecast_after_state_date"
        elif actual_release is not None and actual_release <= state_date:
            reason = "target_already_released"
        elif any(
            pd.isna(row[column])
            for column in ("point_forecast", "lower_80", "upper_80")
        ):
            reason = "forecast_or_interval_missing"
        if reason:
            add(
                "US_GDP_NOWCAST_1A",
                GDP_TARGET,
                gdp_period,
                gdp_stage,
                gdp_model,
                reason,
                [gdp_model],
            )

    def family(
        model_id: str,
        backtest_id: str,
        table: str,
        targets: tuple[str, ...],
        stable_map: dict[str, Any],
    ) -> None:
        target_period = str(pd.Period(state_date, freq="M"))
        stage = "month_end"
        for target in targets:
            expected_model = str(stable_map[target][stage])
            frame = repository.query_df(
                f"""
                SELECT forecast_date, point_forecast, lower_80, upper_80,
                       target_leakage, max_observation_date
                FROM {table}
                WHERE backtest_id = ?
                  AND target_series = ?
                  AND target_period = ?
                  AND forecast_stage = ?
                  AND model_name = ?
                LIMIT 1
                """,
                [
                    backtest_id,
                    target,
                    target_period,
                    stage,
                    expected_model,
                ],
            )
            if frame.empty:
                available = _available_models(
                    repository,
                    table=table,
                    id_column="backtest_id",
                    source_id=backtest_id,
                    target_period=target_period,
                    forecast_stage=stage,
                    target=target,
                )
                add(
                    model_id,
                    target,
                    target_period,
                    stage,
                    expected_model,
                    "stable_model_absent" if available else "target_absent",
                    available,
                )
                continue

            row = frame.iloc[0]
            forecast_date = pd.Timestamp(row["forecast_date"]).date()
            max_observation = (
                pd.Timestamp(row["max_observation_date"]).date()
                if pd.notna(row["max_observation_date"])
                else None
            )
            reason = None
            if forecast_date > state_date:
                reason = "forecast_after_state_date"
            elif bool(row["target_leakage"]):
                reason = "target_leakage"
            elif (
                max_observation is not None
                and max_observation > forecast_date
            ):
                reason = "observation_after_forecast_date"
            elif any(
                pd.isna(row[column])
                for column in ("point_forecast", "lower_80", "upper_80")
            ):
                reason = "forecast_or_interval_missing"
            if reason:
                add(
                    model_id,
                    target,
                    target_period,
                    stage,
                    expected_model,
                    reason,
                    [expected_model],
                )

    family(
        "US_INFLATION_NOWCAST_1B",
        lineage.inflation_backtest_id,
        "inflation_vintage_backtest_results",
        INFLATION_TARGETS,
        policies["inflation"],
    )
    family(
        "US_LABOUR_NOWCAST_1C",
        lineage.labour_backtest_id,
        "labour_vintage_backtest_results",
        LABOUR_TARGETS,
        policies["labour"],
    )
    return pd.DataFrame(gaps)


def diagnose_history_gaps(
    repository: Any,
    states: pd.DataFrame,
) -> pd.DataFrame:
    from macropulse.macro_state.vintage_history import resolve_production_vintage_lineage

    lineage, policies = resolve_production_vintage_lineage(repository)
    frames = [
        diagnose_month(repository, month, lineage, policies)
        for month in missing_month_ends(states)
    ]
    frames = [frame for frame in frames if not frame.empty]
    return (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame()
    )


def joint_regime_distribution(
    *,
    state_date: date,
    growth_score: float,
    inflation_score: float,
    labour_score: float,
    growth_lower: float,
    growth_upper: float,
    inflation_lower: float,
    inflation_upper: float,
    labour_lower: float,
    labour_upper: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    candidate = config["history"]["uncertainty_candidate"]
    draws = int(candidate["draws"])
    correlation = np.asarray(candidate["correlation"], dtype=float)
    if correlation.shape != (3, 3):
        raise ValueError("Uncertainty correlation matrix must be 3x3.")
    if float(np.linalg.eigvalsh(correlation).min()) <= 0.0:
        raise ValueError("Correlation matrix must be positive definite.")

    means = np.asarray(
        [growth_score, inflation_score, labour_score], dtype=float
    )
    widths = np.asarray(
        [
            max(0.0, growth_upper - growth_lower),
            max(0.0, inflation_upper - inflation_lower),
            max(0.0, labour_upper - labour_lower),
        ]
    )
    sigmas = np.maximum(widths / (2.0 * Z80), 1e-9)
    covariance = np.diag(sigmas) @ correlation @ np.diag(sigmas)
    seed = int(candidate["seed"]) + int(
        pd.Timestamp(state_date).strftime("%Y%m%d")
    )
    rng = np.random.default_rng(seed)
    samples = np.clip(
        rng.multivariate_normal(means, covariance, size=draws),
        -2.0,
        2.0,
    )

    counts: dict[str, int] = {}
    for growth, inflation, labour in samples:
        regime = _classify_regime(
            float(growth), float(inflation), float(labour)
        )
        counts[regime] = counts.get(regime, 0) + 1

    probabilities = {
        key: value / draws for key, value in sorted(counts.items())
    }
    top_regime, top_probability = max(
        probabilities.items(), key=lambda item: item[1]
    )
    entropy = -sum(
        p * math.log(p) for p in probabilities.values() if p > 0
    )
    normalized_entropy = (
        entropy / math.log(len(probabilities))
        if len(probabilities) > 1
        else 0.0
    )
    floor = float(candidate["probability_floor"])
    material = {k: v for k, v in probabilities.items() if v >= floor}
    return {
        "state_date": state_date,
        "method": str(candidate["method"]),
        "draws": draws,
        "top_regime": top_regime,
        "top_probability": float(top_probability),
        "normalized_entropy": float(normalized_entropy),
        "effective_regimes": float(math.exp(entropy)),
        "material_regime_count": len(material),
        "probabilities_json": json.dumps(
            probabilities, sort_keys=True
        ),
    }


def uncertainty_table(states: pd.DataFrame) -> pd.DataFrame:
    from macropulse.macro_state.versioning import load_macro_state_governance

    config = load_macro_state_governance()
    rows = []
    for row in states.itertuples(index=False):
        rows.append(
            joint_regime_distribution(
                state_date=pd.Timestamp(row.state_date).date(),
                growth_score=float(row.growth_score),
                inflation_score=float(row.inflation_score),
                labour_score=float(row.labour_score),
                growth_lower=float(row.growth_lower),
                growth_upper=float(row.growth_upper),
                inflation_lower=float(row.inflation_lower),
                inflation_upper=float(row.inflation_upper),
                labour_lower=float(row.labour_lower),
                labour_upper=float(row.labour_upper),
                config=config,
            )
        )
    return pd.DataFrame(rows)


def transition_statistics(
    states: pd.DataFrame,
    minimum_count: int,
) -> pd.DataFrame:
    if states.empty or len(states) < 2:
        return pd.DataFrame()
    ordered = states.sort_values("state_date").copy()
    ordered["_month"] = pd.PeriodIndex(
        ordered["state_date"], freq="M"
    ).asi8
    ordered["to_regime"] = ordered["primary_regime"].shift(-1)
    ordered["_next_month"] = ordered["_month"].shift(-1)
    transitions = ordered.loc[
        ordered["to_regime"].notna()
        & ((ordered["_next_month"] - ordered["_month"]) == 1)
    ]
    if transitions.empty:
        return pd.DataFrame()
    counts = (
        transitions.groupby(
            ["primary_regime", "to_regime"], as_index=False
        )
        .size()
        .rename(
            columns={
                "primary_regime": "from_regime",
                "size": "transition_count",
            }
        )
    )
    totals = (
        counts.groupby("from_regime", as_index=False)[
            "transition_count"
        ]
        .sum()
        .rename(
            columns={
                "transition_count": "from_regime_transitions"
            }
        )
    )
    result = counts.merge(totals, on="from_regime", how="left")
    result["transition_probability"] = (
        result["transition_count"]
        / result["from_regime_transitions"]
    )
    result["meets_minimum_count"] = (
        result["from_regime_transitions"] >= int(minimum_count)
    )
    return result.sort_values(
        ["from_regime", "transition_probability", "to_regime"],
        ascending=[True, False, True],
    ).reset_index(drop=True)
