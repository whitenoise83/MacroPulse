from types import SimpleNamespace

import pandas as pd

from macropulse.services.news_service import _is_no_change_comparison
from scripts.repair_news_reconciliation import _is_legacy_no_change_artifact


WEIGHTS = {"Bridge Ridge": 0.44, "Dynamic Factor Model": 0.56}
COMPONENTS = {"Bridge Ridge": 2.95, "Dynamic Factor Model": 2.63}


def test_no_change_comparison_is_detected() -> None:
    assert _is_no_change_comparison(
        release_changes=pd.DataFrame(),
        previous_weights=WEIGHTS,
        current_weights=WEIGHTS,
        previous_components=COMPONENTS,
        current_components=COMPONENTS,
        total_change=0.0,
    )


def test_data_change_prevents_no_change_short_circuit() -> None:
    changes = pd.DataFrame([{"series_id": "PAYEMS", "change_type": "new"}])
    assert not _is_no_change_comparison(
        release_changes=changes,
        previous_weights=WEIGHTS,
        current_weights=WEIGHTS,
        previous_components=COMPONENTS,
        current_components=COMPONENTS,
        total_change=0.0,
    )


def test_legacy_false_residual_is_repairable() -> None:
    row = SimpleNamespace(status="success", total_change=0.0, residual_interaction=0.026611, dfm_refit_impact=-0.026611)
    details = {
        "raw_change_counts": {},
        "dfm_update_count": 0,
        "dfm_revision_count": 0,
        "previous_weights": WEIGHTS,
        "current_weights": WEIGHTS,
        "previous_components": COMPONENTS,
        "current_components": COMPONENTS,
    }
    assert _is_legacy_no_change_artifact(row, details)


def test_build_news_decomposition_short_circuits_identical_runs() -> None:
    import json
    from macropulse.services.news_service import build_news_decomposition

    class FakeRepository:
        def __init__(self) -> None:
            self.saved = None
            self.observations = pd.DataFrame(
                [
                    {
                        "series_id": "PAYEMS",
                        "observation_date": pd.Timestamp("2026-06-30"),
                        "value": 1.0,
                        "retrieved_at": pd.Timestamp("2026-07-01"),
                    }
                ]
            )

        def load_information_set(self, run_id: str) -> pd.DataFrame:
            return self.observations.copy()

        def query_df(self, query: str, params: list[str]) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "model_name": ["Bridge Ridge", "Dynamic Factor Model"],
                    "point_forecast": [2.957732711591355, 2.6339739202223984],
                }
            )

        def save_news_outputs(self, news_run, contributions, release_changes) -> None:
            self.saved = (news_run.copy(), contributions.copy(), release_changes.copy())

    repository = FakeRepository()
    previous_run = pd.Series(
        {
            "run_id": "previous",
            "data_as_of": pd.Timestamp("2026-07-28"),
            "metrics_json": json.dumps({"production_weights": WEIGHTS}),
        }
    )
    result = build_news_decomposition(
        repository=repository,
        previous_run=previous_run,
        current_run_id="current",
        current_observations=repository.observations.copy(),
        current_bridge_fit=object(),
        current_dfm_fit=object(),
        current_weights=WEIGHTS,
        definitions=[],
        target_series="GDPC1",
        target_period=pd.Period("2026Q2", freq="Q"),
        ridge_alpha=1.0,
        interval=0.80,
        dfm_config={},
    )

    assert result["status"] == "success"
    assert result["total_change"] == 0.0
    assert result["details"]["decomposition_kind"] == "no_change"
    news_run, contributions, release_changes = repository.saved
    assert float(news_run.iloc[0]["residual_interaction"]) == 0.0
    assert contributions.empty
    assert release_changes.empty


def test_weight_only_comparison_is_detected() -> None:
    from macropulse.services.news_service import _is_weight_only_comparison

    current_weights = {"Bridge Ridge": 0.0, "Dynamic Factor Model": 1.0}
    expected_change = (
        (current_weights["Bridge Ridge"] - WEIGHTS["Bridge Ridge"])
        * COMPONENTS["Bridge Ridge"]
        + (
            current_weights["Dynamic Factor Model"]
            - WEIGHTS["Dynamic Factor Model"]
        )
        * COMPONENTS["Dynamic Factor Model"]
    )
    assert _is_weight_only_comparison(
        release_changes=pd.DataFrame(),
        previous_weights=WEIGHTS,
        current_weights=current_weights,
        previous_components=COMPONENTS,
        current_components=COMPONENTS,
        total_change=expected_change,
    )


def test_legacy_weight_only_false_residual_is_repairable() -> None:
    from scripts.repair_news_reconciliation import _is_legacy_weight_only_artifact

    current_weights = {"Bridge Ridge": 0.0, "Dynamic Factor Model": 1.0}
    total_change = (
        (current_weights["Bridge Ridge"] - WEIGHTS["Bridge Ridge"])
        * COMPONENTS["Bridge Ridge"]
        + (
            current_weights["Dynamic Factor Model"]
            - WEIGHTS["Dynamic Factor Model"]
        )
        * COMPONENTS["Dynamic Factor Model"]
    )
    row = SimpleNamespace(status="success", total_change=total_change, residual_interaction=0.026611, dfm_refit_impact=-0.026611)
    details = {
        "raw_change_counts": {},
        "dfm_update_count": 0,
        "dfm_revision_count": 0,
        "previous_weights": WEIGHTS,
        "current_weights": current_weights,
        "previous_components": COMPONENTS,
        "current_components": COMPONENTS,
    }
    assert _is_legacy_weight_only_artifact(row, details)


def test_build_news_decomposition_short_circuits_weight_only_run() -> None:
    import json

    from macropulse.services.news_service import build_news_decomposition

    current_weights = {"Bridge Ridge": 0.0, "Dynamic Factor Model": 1.0}

    class FakeRepository:
        def __init__(self) -> None:
            self.saved = None
            self.observations = pd.DataFrame(
                [
                    {
                        "series_id": "PAYEMS",
                        "observation_date": pd.Timestamp("2026-06-30"),
                        "value": 1.0,
                        "retrieved_at": pd.Timestamp("2026-07-01"),
                    }
                ]
            )

        def load_information_set(self, run_id: str) -> pd.DataFrame:
            return self.observations.copy()

        def query_df(self, query: str, params: list[str]) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "model_name": ["Bridge Ridge", "Dynamic Factor Model"],
                    "point_forecast": [2.957732711591355, 2.6339739202223984],
                }
            )

        def save_news_outputs(self, news_run, contributions, release_changes) -> None:
            self.saved = (news_run.copy(), contributions.copy(), release_changes.copy())

    repository = FakeRepository()
    previous_run = pd.Series(
        {
            "run_id": "previous",
            "data_as_of": pd.Timestamp("2026-07-28"),
            "metrics_json": json.dumps({"production_weights": WEIGHTS}),
        }
    )
    result = build_news_decomposition(
        repository=repository,
        previous_run=previous_run,
        current_run_id="current",
        current_observations=repository.observations.copy(),
        current_bridge_fit=object(),
        current_dfm_fit=object(),
        current_weights=current_weights,
        definitions=[],
        target_series="GDPC1",
        target_period=pd.Period("2026Q2", freq="Q"),
        ridge_alpha=1.0,
        interval=0.80,
        dfm_config={},
    )

    assert result["status"] == "success"
    assert result["details"]["decomposition_kind"] == "weight_only"
    news_run, contributions, release_changes = repository.saved
    assert float(news_run.iloc[0]["residual_interaction"]) == 0.0
    assert float(news_run.iloc[0]["dfm_refit_impact"]) == 0.0
    assert len(contributions) == 1
    assert contributions.iloc[0]["contribution_type"] == "weight_change"
    assert release_changes.empty
