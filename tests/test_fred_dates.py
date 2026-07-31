from datetime import date

import pandas as pd

from macropulse.data.fred_client import _parse_fred_dates


def test_open_ended_alfred_date_is_preserved() -> None:
    parsed = _parse_fred_dates(pd.Series(["2026-07-29", "9999-12-31", "."]))
    assert parsed.iloc[0] == date(2026, 7, 29)
    assert parsed.iloc[1] == date.max
    assert pd.isna(parsed.iloc[2])
