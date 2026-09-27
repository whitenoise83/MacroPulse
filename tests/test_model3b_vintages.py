from datetime import date

import pandas as pd
import pytest

from macropulse.slack.vintages import (
    canonical_snapshot_hash,
    derive_information_set_inventory,
    information_set_id,
    validate_information_set_inventory,
)


def make_snapshot(last_quarter: int):
    rows = []
    for q in range(1, last_quarter + 1):
        month = 1 + (q - 1) * 3
        rows.append(("GDPC1", f"2020-{month:02d}-01", 100.0 + q))
        for offset in range(3):
            m = month + offset
            rows.append(("PCEPILFE", f"2020-{m:02d}-01", 100.0 + m))
            rows.append(("UNRATE", f"2020-{m:02d}-01", 4.0 + m / 10.0))
    return pd.DataFrame(rows, columns=["series_id", "observation_date", "value"])


def test_hash_and_id_are_deterministic():
    s = make_snapshot(2)
    d = date(2020, 6, 30)
    h1 = canonical_snapshot_hash(s, d)
    h2 = canonical_snapshot_hash(s.sample(frac=1, random_state=7), d)
    assert h1 == h2
    assert information_set_id(d, h1) == information_set_id(d, h2)


def test_inventory_marks_first_state_left_censored():
    cutoffs = [date(2020, 6, 30), date(2020, 9, 30)]
    snapshots = {
        cutoffs[0]: make_snapshot(2),
        cutoffs[1]: make_snapshot(3),
    }
    inv = derive_information_set_inventory(cutoffs, snapshots.__getitem__)
    assert len(inv) == 2
    assert bool(inv.iloc[0]["left_censored"]) is True
    assert bool(inv.iloc[0]["admissible_for_pseudo_real_time"]) is False
    assert bool(inv.iloc[1]["admissible_for_pseudo_real_time"]) is True
    validate_information_set_inventory(inv)


def test_inventory_rejects_skipped_terminal_quarter():
    cutoffs = [date(2020, 6, 30), date(2020, 12, 31)]
    snapshots = {
        cutoffs[0]: make_snapshot(2),
        cutoffs[1]: make_snapshot(4),
    }
    with pytest.raises(ValueError, match="skipped"):
        derive_information_set_inventory(cutoffs, snapshots.__getitem__)
