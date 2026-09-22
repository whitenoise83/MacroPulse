from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from macropulse.bvar.model import FORECAST_HORIZONS
from macropulse.bvar.production import (
    MODEL2_VERSION,
    PLANNED_RELEASE_TAG,
    PRODUCTION_HORIZONS,
    SELECTED_CANDIDATE_ID,
    SELECTED_LAGS,
    SELECTED_SHRINKAGE,
    SELECTION_EVIDENCE_PAYLOAD_HASH,
    run_model2_forecast,
    selected_candidate,
)


def synthetic_snapshot() -> tuple[pd.DataFrame, date]:
    rows = []

    quarters = pd.period_range("2000Q1", "2015Q4", freq="Q")
    for i, quarter in enumerate(quarters):
        rows.append(
            {
                "series_id": "GDPC1",
                "observation_date": quarter.end_time.date(),
                "value": 10000.0
                * np.exp(0.006 * i + 0.00035 * np.sin(i / 2.5)),
            }
        )

    months = pd.period_range("2000-01", "2015-12", freq="M")
    for i, month in enumerate(months):
        observation_date = month.end_time.date()
        rows.extend(
            [
                {
                    "series_id": "PCEPILFE",
                    "observation_date": observation_date,
                    "value": 80.0
                    * np.exp(0.0018 * i + 0.00025 * np.sin(i / 5.0)),
                },
                {
                    "series_id": "UNRATE",
                    "observation_date": observation_date,
                    "value": 5.0 + 0.25 * np.sin(i / 12.0),
                },
                {
                    "series_id": "FEDFUNDS",
                    "observation_date": observation_date,
                    "value": 2.0 + 0.35 * np.sin(i / 18.0),
                },
            ]
        )

    return pd.DataFrame.from_records(rows), date(2016, 1, 31)


def test_selected_candidate_constants_are_frozen() -> None:
    assert SELECTED_CANDIDATE_ID == "a69878bf644615c5"
    assert SELECTED_LAGS == 2
    assert SELECTED_SHRINKAGE == pytest.approx(0.1)
    assert SELECTION_EVIDENCE_PAYLOAD_HASH == (
        "2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7"
    )


def test_selected_candidate_matches_model2c_grid() -> None:
    candidate = selected_candidate()
    assert candidate.candidate_id == SELECTED_CANDIDATE_ID
    assert candidate.lags == SELECTED_LAGS
    assert candidate.shrinkage == pytest.approx(SELECTED_SHRINKAGE)


def test_release_identity_is_frozen() -> None:
    assert MODEL2_VERSION == "1.0.0"
    assert PLANNED_RELEASE_TAG == "model2-bvar-v1.0.0"
    assert PRODUCTION_HORIZONS == tuple(FORECAST_HORIZONS)


def test_release_forecast_contains_governed_outputs() -> None:
    snapshot, cutoff = synthetic_snapshot()
    result = run_model2_forecast(snapshot, cutoff, simulations=100, seed=123)

    assert result.candidate_id == SELECTED_CANDIDATE_ID
    assert result.lags == 2
    assert result.shrinkage == pytest.approx(0.1)
    assert result.information_cutoff == cutoff
    assert result.estimation_last_quarter == "2015Q4"
    assert result.estimation_observations >= 50
    assert len(result.point_forecast) == 4
    assert len(result.predictive_summary) == 16
    assert len(result.structural_irf) == 64
    assert len(result.structural_fevd) == 64


def test_target_quarters_follow_origin() -> None:
    snapshot, cutoff = synthetic_snapshot()
    result = run_model2_forecast(snapshot, cutoff, simulations=100, seed=123)
    assert result.point_forecast["target_quarter"].tolist() == [
        "2016Q1",
        "2016Q2",
        "2016Q4",
        "2017Q4",
    ]


def test_predictive_intervals_are_ordered() -> None:
    snapshot, cutoff = synthetic_snapshot()
    result = run_model2_forecast(snapshot, cutoff, simulations=100, seed=123)
    summary = result.predictive_summary
    for suffix in (50, 80, 95):
        assert bool(
            (
                summary[f"lower_{suffix}"]
                <= summary[f"upper_{suffix}"]
            ).all()
        )


def test_same_seed_is_reproducible_at_hash_level() -> None:
    snapshot, cutoff = synthetic_snapshot()
    first = run_model2_forecast(snapshot, cutoff, simulations=100, seed=123)
    second = run_model2_forecast(snapshot, cutoff, simulations=100, seed=123)
    assert first.predictive_draw_hash == second.predictive_draw_hash
    assert first.output_fingerprint == second.output_fingerprint
    pd.testing.assert_frame_equal(
        first.predictive_summary,
        second.predictive_summary,
    )


def test_different_seed_changes_predictive_identity() -> None:
    snapshot, cutoff = synthetic_snapshot()
    first = run_model2_forecast(snapshot, cutoff, simulations=100, seed=123)
    second = run_model2_forecast(snapshot, cutoff, simulations=100, seed=124)
    assert first.predictive_draw_hash != second.predictive_draw_hash
    assert first.output_fingerprint != second.output_fingerprint


def test_source_snapshot_hash_is_row_order_invariant() -> None:
    snapshot, cutoff = synthetic_snapshot()
    first = run_model2_forecast(snapshot, cutoff, simulations=100, seed=123)
    shuffled = snapshot.sample(
        frac=1.0,
        random_state=42,
    ).reset_index(drop=True)
    second = run_model2_forecast(shuffled, cutoff, simulations=100, seed=123)
    assert first.source_snapshot_hash == second.source_snapshot_hash
    assert first.estimation_panel_hash == second.estimation_panel_hash
    assert first.output_fingerprint == second.output_fingerprint


def test_future_observation_row_fails_closed() -> None:
    snapshot, cutoff = synthetic_snapshot()
    future = pd.DataFrame(
        [
            {
                "series_id": "UNRATE",
                "observation_date": date(2016, 2, 29),
                "value": 5.0,
            }
        ]
    )
    altered = pd.concat([snapshot, future], ignore_index=True)

    with pytest.raises(ValueError, match="later than as_of_date"):
        run_model2_forecast(altered, cutoff, simulations=100, seed=123)


def test_too_few_simulations_fails_closed() -> None:
    snapshot, cutoff = synthetic_snapshot()
    with pytest.raises(ValueError, match="at least 100"):
        run_model2_forecast(snapshot, cutoff, simulations=99, seed=123)


def test_invalid_cutoff_type_fails_closed() -> None:
    snapshot, _ = synthetic_snapshot()
    with pytest.raises(ValueError, match="datetime.date"):
        run_model2_forecast(
            snapshot,
            "2016-01-31",  # type: ignore[arg-type]
            simulations=100,
            seed=123,
        )


def test_structural_outputs_use_governed_horizons() -> None:
    snapshot, cutoff = synthetic_snapshot()
    result = run_model2_forecast(snapshot, cutoff, simulations=100, seed=123)
    assert set(result.structural_irf["horizon"]) == {1, 4, 8, 12}
    assert set(result.structural_fevd["horizon"]) == {1, 4, 8, 12}


def test_fevd_adds_to_one() -> None:
    snapshot, cutoff = synthetic_snapshot()
    result = run_model2_forecast(snapshot, cutoff, simulations=100, seed=123)
    totals = result.structural_fevd.groupby(
        ["horizon", "response"]
    )["share"].sum()
    np.testing.assert_allclose(
        totals.to_numpy(dtype=float),
        1.0,
        rtol=0.0,
        atol=1e-12,
    )
