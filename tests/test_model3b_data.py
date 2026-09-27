from datetime import date
from math import isclose, log

import pandas as pd
import pytest

from macropulse.slack.data import build_quarterly_panel, normalise_snapshot


def snapshot():
    rows = []
    for d, v in [("2020-01-01", 100.0), ("2020-04-01", 102.0), ("2020-07-01", 104.0)]:
        rows.append(("GDPC1", d, v))
    for d, v in [
        ("2020-01-01", 100.0), ("2020-02-01", 101.0), ("2020-03-01", 102.0),
        ("2020-04-01", 103.0), ("2020-05-01", 104.0), ("2020-06-01", 105.0),
        ("2020-07-01", 106.0), ("2020-08-01", 107.0), ("2020-09-01", 108.0),
    ]:
        rows.append(("PCEPILFE", d, v))
    for d, v in [
        ("2020-01-01", 4.0), ("2020-02-01", 4.1), ("2020-03-01", 4.2),
        ("2020-04-01", 5.0), ("2020-05-01", 5.1), ("2020-06-01", 5.2),
        ("2020-07-01", 6.0), ("2020-08-01", 6.1), ("2020-09-01", 6.2),
    ]:
        rows.append(("UNRATE", d, v))
    return pd.DataFrame(rows, columns=["series_id", "observation_date", "value"])


def test_panel_preserves_gdp_level_and_log():
    panel = build_quarterly_panel(snapshot(), date(2020, 9, 30))
    assert list(panel.index.astype(str)) == ["2020Q2", "2020Q3"]
    assert panel.loc[pd.Period("2020Q3"), "real_gdp_level"] == 104.0
    assert isclose(panel.loc[pd.Period("2020Q3"), "real_gdp_log"], log(104.0))


def test_quarter_end_unemployment():
    panel = build_quarterly_panel(snapshot(), date(2020, 9, 30))
    assert panel.loc[pd.Period("2020Q2"), "unemployment_rate"] == 5.2
    assert panel.loc[pd.Period("2020Q3"), "unemployment_rate"] == 6.2


def test_core_pce_inflation_is_annualised_qoq_log_change():
    panel = build_quarterly_panel(snapshot(), date(2020, 9, 30))
    expected = 400.0 * (log(108.0) - log(105.0))
    assert isclose(panel.loc[pd.Period("2020Q3"), "core_pce_inflation"], expected)


def test_future_observation_rejected():
    s = snapshot()
    extra = pd.DataFrame([["UNRATE", "2021-01-01", 7.0]], columns=s.columns)
    with pytest.raises(ValueError, match="later than as_of_date"):
        normalise_snapshot(pd.concat([s, extra], ignore_index=True), date(2020, 9, 30))


def test_duplicate_exact_vintage_row_rejected():
    s = snapshot()
    with pytest.raises(ValueError, match="duplicate exact-vintage"):
        normalise_snapshot(pd.concat([s, s.iloc[[0]]], ignore_index=True), date(2020, 9, 30))
