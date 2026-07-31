from pathlib import Path

import pandas as pd

from macropulse.governance.versioning import code_hash, information_set_hash


def test_code_hash_changes_when_code_changes(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    file_path = tmp_path / "src" / "model.py"
    file_path.write_text("x = 1\n", encoding="utf-8")
    first = code_hash(tmp_path)
    assert first == code_hash(tmp_path)
    file_path.write_text("x = 2\n", encoding="utf-8")
    assert first != code_hash(tmp_path)


def test_information_set_hash_is_order_invariant() -> None:
    frame = pd.DataFrame(
        [
            {"series_id": "B", "observation_date": "2024-02-01", "value": 2.0},
            {"series_id": "A", "observation_date": "2024-01-01", "value": 1.0},
        ]
    )
    assert information_set_hash(frame) == information_set_hash(frame.iloc[::-1])
