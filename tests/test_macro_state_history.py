from __future__ import annotations

from datetime import date

import pandas as pd

from macropulse.macro_state.history import (
    month_end_dates,
    possible_regimes_from_intervals,
    reconstruction_dates,
    regime_durations,
    transition_matrix,
)


def test_month_end_dates_are_deterministic() -> None:
    assert month_end_dates(
        date(2026, 1, 1),
        date(2026, 3, 31),
    ) == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]



def test_reconstruction_dates_include_explicit_terminal_as_of_date() -> None:
    assert reconstruction_dates(
        date(2026, 7, 1),
        date(2026, 8, 1),
    ) == [
        date(2026, 7, 31),
        date(2026, 8, 1),
    ]


def test_reconstruction_dates_do_not_duplicate_month_end() -> None:
    assert reconstruction_dates(
        date(2026, 7, 1),
        date(2026, 7, 31),
    ) == [date(2026, 7, 31)]

def test_possible_regimes_include_point_consistent_states() -> None:
    regimes = possible_regimes_from_intervals(
        0.3, 1.2,
        -1.2, -0.2,
        -0.2, 0.8,
    )
    assert "disinflationary_expansion" in regimes
    assert len(regimes) >= 1


def test_transition_matrix_and_durations() -> None:
    states = pd.DataFrame(
        {
            "state_date": pd.to_datetime(
                [
                    "2026-01-31",
                    "2026-02-28",
                    "2026-03-31",
                    "2026-04-30",
                ]
            ).date,
            "primary_regime": [
                "balanced_expansion",
                "balanced_expansion",
                "reflation",
                "reflation",
            ],
            "primary_regime_label": [
                "Balanced expansion",
                "Balanced expansion",
                "Reflation",
                "Reflation",
            ],
        }
    )
    durations = regime_durations(states)
    assert durations["primary_regime"].tolist() == [
        "balanced_expansion",
        "reflation",
    ]
    assert durations["primary_regime_label"].tolist() == [
        "Balanced expansion",
        "Reflation",
    ]
    assert durations["months"].tolist() == [2, 2]
    matrix = transition_matrix(states)
    assert matrix.loc["balanced_expansion", "balanced_expansion"] == 0.5
    assert matrix.loc["balanced_expansion", "reflation"] == 0.5
    assert matrix.loc["reflation", "reflation"] == 1.0

def test_duration_segments_split_on_missing_months() -> None:
    states = pd.DataFrame(
        {
            "state_date": pd.to_datetime(
                ["2026-01-31", "2026-03-31"]
            ).date,
            "primary_regime": [
                "balanced_expansion",
                "balanced_expansion",
            ],
            "primary_regime_label": [
                "Balanced expansion",
                "Balanced expansion",
            ],
        }
    )
    durations = regime_durations(states)
    assert durations["months"].tolist() == [1, 1]


def test_transition_matrix_excludes_noncontiguous_months() -> None:
    states = pd.DataFrame(
        {
            "state_date": pd.to_datetime(
                ["2026-01-31", "2026-03-31"]
            ).date,
            "primary_regime": [
                "balanced_expansion",
                "reflation",
            ],
            "primary_regime_label": [
                "Balanced expansion",
                "Reflation",
            ],
        }
    )
    assert transition_matrix(states).empty

