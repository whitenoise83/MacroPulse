from __future__ import annotations

from datetime import date

from macropulse.macro_state.vintage_history import gdp_stage_for_month


def test_gdp_month_stage_alignment() -> None:
    assert gdp_stage_for_month(date(2026, 1, 31)) == "early_quarter"
    assert gdp_stage_for_month(date(2026, 2, 28)) == "after_month_1"
    assert gdp_stage_for_month(date(2026, 3, 31)) == "quarter_end"
    assert gdp_stage_for_month(date(2026, 4, 30)) == "early_quarter"
