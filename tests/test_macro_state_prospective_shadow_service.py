from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import macropulse.macro_state.prospective_shadow_service as service


def _current_inputs() -> pd.DataFrame:
    specs = [
        ("GDPC1", "US_GDP_NOWCAST_1A", "gdp-run", 2.8, 1.8, 3.8),
        ("PCEPILFE", "US_INFLATION_NOWCAST_1B", "inflation-run", 3.0, 2.4, 3.6),
        ("CPILFESL", "US_INFLATION_NOWCAST_1B", "inflation-run", 3.2, 2.6, 3.8),
        ("PCEPI", "US_INFLATION_NOWCAST_1B", "inflation-run", 2.8, 2.2, 3.4),
        ("CPIAUCSL", "US_INFLATION_NOWCAST_1B", "inflation-run", 3.1, 2.5, 3.7),
        ("PAYEMS", "US_LABOUR_NOWCAST_1C", "labour-run", 150.0, 90.0, 210.0),
        ("UNRATE", "US_LABOUR_NOWCAST_1C", "labour-run", 4.2, 3.9, 4.5),
        ("CES0500000003", "US_LABOUR_NOWCAST_1C", "labour-run", 3.8, 3.2, 4.4),
    ]
    return pd.DataFrame(
        [
            {
                "run_id": "macro-run",
                "source_target": target,
                "source_target_name": target,
                "target_period": "2026-08",
                "forecast_stage": "month_end",
                "source_model_id": model_id,
                "source_model_version": "1.0.0",
                "source_run_id": run_id,
                "point_forecast": point,
                "lower_80": lower,
                "upper_80": upper,
                "information_cutoff": date(2026, 8, 5),
                "data_as_of": date(2026, 8, 5),
                "source_hash": (target.lower() + "0" * 64)[:64],
                "created_at": pd.Timestamp("2026-08-05 10:00:00"),
            }
            for target, model_id, run_id, point, lower, upper in specs
        ]
    )


def _history() -> pd.DataFrame:
    rows = []
    current = _current_inputs().set_index("source_target")
    for index, state_date in enumerate(
        pd.date_range("2024-01-31", periods=24, freq="ME")
    ):
        for target in current.index:
            rows.append(
                {
                    "state_date": state_date.date(),
                    "source_target": target,
                    "point_forecast": float(
                        current.loc[target, "point_forecast"]
                    ) + (index % 5 - 2) * 0.05,
                }
            )
    return pd.DataFrame(rows)


class FakeRepository:
    def __init__(self, *, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.saved = None
        self.initialised = False

    def initialise(self) -> None:
        self.initialised = True

    def query_df(self, query: str, parameters=None) -> pd.DataFrame:
        normalised = " ".join(query.split())
        if "FROM macro_state_shadow_runs" in normalised:
            return (
                pd.DataFrame([{"shadow_run_id": "existing"}])
                if self.duplicate
                else pd.DataFrame(columns=["shadow_run_id"])
            )
        if "FROM macro_state_history_runs" in normalised:
            return pd.DataFrame([{"reconstruction_id": "hist-1"}])
        if "FROM macro_state_history_inputs" in normalised:
            return _history()
        if "FROM macro_state_shadow_outcomes" in normalised:
            return pd.DataFrame(
                columns=[
                    "state_date",
                    "primary_family",
                    "state_available_date",
                ]
            )
        raise AssertionError(f"Unexpected query: {normalised}")

    def save_macro_state_shadow_predictions(
        self,
        run_record: pd.DataFrame,
        predictions: pd.DataFrame,
        dimensions: pd.DataFrame,
    ) -> None:
        self.saved = (
            run_record.copy(),
            predictions.copy(),
            dimensions.copy(),
        )


def _write_project(root: Path) -> None:
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    source = Path("config") / "macro_state_governance.yml"
    (config_dir / "macro_state_governance.yml").write_text(
        source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    report = (
        root
        / "reports"
        / "macro_state_fixed_horizon_probabilistic"
    )
    report.mkdir(parents=True)
    stem = (
        "model1d_fixed_horizon_"
        "c99ac096-a9cb-4e39-b976-b0d4cfe018a1"
    )
    pd.DataFrame(
        [
            {
                "state_date": date(2025, month, 28),
                "primary_family": family,
                "state_available_date": date(2025, month, 28)
                + pd.Timedelta(days=90),
            }
            for month, family in [
                (1, "mixed"),
                (2, "benign_expansion"),
                (3, "inflationary_expansion"),
                (4, "mixed"),
                (5, "contraction"),
                (6, "adverse_supply"),
                (7, "mixed"),
                (8, "benign_expansion"),
                (9, "inflationary_expansion"),
                (10, "mixed"),
                (11, "contraction"),
                (12, "mixed"),
            ]
        ]
    ).to_csv(report / f"{stem}_locked_targets.csv", index=False)


def _patch_runtime(monkeypatch, project_root: Path) -> None:
    monkeypatch.setattr(
        service,
        "current_macro_state_identity",
        lambda root: SimpleNamespace(
            model_id="US_MACRO_STATE_1D",
            model_version="0.3.8",
            lifecycle_status="development",
            config_hash="a" * 64,
            code_hash="b" * 64,
            git_commit="test",
        ),
    )
    monkeypatch.setattr(
        service,
        "run_macro_state",
        lambda repository, as_of: {
            "run_id": "macro-run",
            "inputs": _current_inputs(),
            "source_bundle_hash": "c" * 64,
        },
    )
    monkeypatch.setattr(
        service,
        "_utc_now_naive",
        lambda: pd.Timestamp("2026-08-05 10:30:00"),
    )


def test_service_persists_one_two_three_bundle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_project(tmp_path)
    _patch_runtime(monkeypatch, tmp_path)
    repository = FakeRepository()

    result = service.run_macro_state_prospective_shadow(
        repository=repository,
        as_of=date(2026, 8, 5),
        project_root=tmp_path,
    )

    assert repository.initialised is True
    assert repository.saved is not None
    run_record, predictions, dimensions = repository.saved
    assert len(run_record) == 1
    assert set(predictions["benchmark_id"]) == {
        "source",
        "rolling_frequency",
    }
    assert set(dimensions["dimension"]) == {
        "growth",
        "inflation",
        "labour",
    }
    assert result["promotion_authority"] == "none"
    assert result["governance"]["status"] == "pass"
    assert result["target_expected_available_date"] == date(2026, 11, 29)
    assert len(result["information_set_hash"]) == 64


def test_duplicate_month_is_rejected_before_macro_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_project(tmp_path)
    called = {"macro": False}
    monkeypatch.setattr(
        service,
        "current_macro_state_identity",
        lambda root: SimpleNamespace(
            model_id="US_MACRO_STATE_1D",
            model_version="0.3.8",
            lifecycle_status="development",
            config_hash="a" * 64,
            code_hash="b" * 64,
            git_commit="test",
        ),
    )
    monkeypatch.setattr(
        service,
        "run_macro_state",
        lambda repository, as_of: called.update(macro=True),
    )
    monkeypatch.setattr(
        service,
        "_utc_now_naive",
        lambda: pd.Timestamp("2026-08-05 10:30:00"),
    )

    with pytest.raises(ValueError, match="append-only violation"):
        service.run_macro_state_prospective_shadow(
            repository=FakeRepository(duplicate=True),
            as_of=date(2026, 8, 5),
            project_root=tmp_path,
        )
    assert called["macro"] is False
