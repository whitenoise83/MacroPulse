from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from macropulse.bvar.data import audit_snapshot, build_complete_quarter_panel


ROOT = Path(__file__).parents[1]


def row(series_id: str, observation_date: str, value: float) -> dict:
    return {
        "series_id": series_id,
        "observation_date": observation_date,
        "value": value,
    }


def complete_snapshot() -> pd.DataFrame:
    rows = [
        row("GDPC1", "2023-10-01", 100.0),
        row("GDPC1", "2024-01-01", 101.0),
        row("GDPC1", "2024-04-01", 102.0),
        row("PCEPILFE", "2023-10-01", 100.0),
        row("PCEPILFE", "2023-11-01", 100.5),
        row("PCEPILFE", "2023-12-01", 101.0),
        row("PCEPILFE", "2024-01-01", 101.2),
        row("PCEPILFE", "2024-02-01", 101.4),
        row("PCEPILFE", "2024-03-01", 101.8),
        row("PCEPILFE", "2024-04-01", 102.0),
        row("PCEPILFE", "2024-05-01", 102.2),
        row("PCEPILFE", "2024-06-01", 102.6),
    ]
    for month, unrate, ff in [
        ("2023-10-01", 3.8, 5.33),
        ("2023-11-01", 3.7, 5.33),
        ("2023-12-01", 3.7, 5.33),
        ("2024-01-01", 3.7, 5.33),
        ("2024-02-01", 3.9, 5.33),
        ("2024-03-01", 3.8, 5.33),
        ("2024-04-01", 3.9, 5.33),
        ("2024-05-01", 4.0, 5.33),
        ("2024-06-01", 4.1, 5.33),
    ]:
        rows.append(row("UNRATE", month, unrate))
        rows.append(row("FEDFUNDS", month, ff))
    return pd.DataFrame(rows)


def test_complete_panel_requires_prior_quarter_for_log_growth() -> None:
    panel = build_complete_quarter_panel(
        complete_snapshot(),
        date(2024, 7, 31),
    )
    assert list(panel.index.astype(str)) == ["2024Q1", "2024Q2"]
    assert list(panel.columns) == [
        "real_gdp_growth",
        "core_pce_inflation",
        "unemployment_rate",
        "policy_rate",
    ]


def test_pce_requires_quarter_end_month() -> None:
    snapshot = complete_snapshot()
    snapshot = snapshot[
        ~(
            snapshot["series_id"].eq("PCEPILFE")
            & snapshot["observation_date"].eq("2024-06-01")
        )
    ]
    panel = build_complete_quarter_panel(snapshot, date(2024, 7, 31))
    assert "2024Q2" not in panel.index.astype(str)


def test_unrate_uses_quarter_end_month_not_three_month_average() -> None:
    snapshot = complete_snapshot()
    snapshot = snapshot[
        ~(
            snapshot["series_id"].eq("UNRATE")
            & snapshot["observation_date"].eq("2024-05-01")
        )
    ]
    panel = build_complete_quarter_panel(snapshot, date(2024, 7, 31))
    assert "2024Q2" in panel.index.astype(str)
    assert panel.loc[pd.Period("2024Q2", freq="Q"), "unemployment_rate"] == pytest.approx(4.1)


def test_unrate_requires_quarter_end_month() -> None:
    snapshot = complete_snapshot()
    snapshot = snapshot[
        ~(
            snapshot["series_id"].eq("UNRATE")
            & snapshot["observation_date"].eq("2024-06-01")
        )
    ]
    panel = build_complete_quarter_panel(snapshot, date(2024, 7, 31))
    assert "2024Q2" not in panel.index.astype(str)


def test_policy_rate_still_requires_all_three_months() -> None:
    snapshot = complete_snapshot()
    snapshot = snapshot[
        ~(
            snapshot["series_id"].eq("FEDFUNDS")
            & snapshot["observation_date"].eq("2024-05-01")
        )
    ]
    panel = build_complete_quarter_panel(snapshot, date(2024, 7, 31))
    assert "2024Q2" not in panel.index.astype(str)


def test_future_observation_is_rejected() -> None:
    snapshot = complete_snapshot()
    snapshot.loc[len(snapshot)] = row("UNRATE", "2024-08-01", 4.2)
    with pytest.raises(ValueError, match="later than as_of_date"):
        build_complete_quarter_panel(snapshot, date(2024, 7, 31))


def test_audit_reports_joint_panel_and_lag() -> None:
    audit = audit_snapshot(complete_snapshot(), date(2024, 7, 31))
    assert audit.complete_joint_quarters == 2
    assert audit.first_joint_quarter == "2024Q1"
    assert audit.last_joint_quarter == "2024Q2"
    assert audit.lag_quarters == 1
    assert audit.notices == ()


def test_missing_series_is_explicit() -> None:
    snapshot = complete_snapshot()
    snapshot = snapshot[snapshot["series_id"] != "FEDFUNDS"]
    audit = audit_snapshot(snapshot, date(2024, 7, 31))
    assert "missing_series:FEDFUNDS" in audit.notices
    assert audit.complete_joint_quarters == 0


def test_model2_ci_guard_contract() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
    ).read_text(encoding="utf-8")

    required = (
        "name: Model 2 Bayesian VAR Guard",
        "- model2-bvar-development",
        "python scripts/verify_phase2_release.py --require-tag",
        "python scripts/verify_model1d_v038_release.py --require-tags",
        "python scripts/verify_phase3_evaluation.py",
        "python scripts/verify_phase3_release.py --require-tag",
        "python scripts/verify_model2b_data_vintage_scaffold.py",
        "python -m pytest -q --disable-warnings tests/test_model2b_data_vintage.py",
        "python -m pytest -q --disable-warnings",
    )
    for token in required:
        assert token in workflow
