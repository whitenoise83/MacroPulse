from __future__ import annotations

import json

from macropulse.inflation.validation import _check, _json_safe


def test_json_safe_converts_multiindex_tuple_keys() -> None:
    details = {
        ("CPILFESL", "month_end"): 42,
        ("PCEPILFE", "pre_release"): {"models": {"AR", "Ridge"}},
    }

    normalised = _json_safe(details)
    assert normalised["CPILFESL | month_end"] == 42
    assert normalised["PCEPILFE | pre_release"]["models"] == ["AR", "Ridge"]


def test_check_serialises_tuple_keyed_details_as_valid_json() -> None:
    result = _check(
        "Econometric validity",
        "Minimum evaluated months",
        "pass",
        36,
        ">= 36",
        {("CPIAUCSL", "month_open"): 139},
    )

    decoded = json.loads(result["details_json"])
    assert decoded == {"CPIAUCSL | month_open": 139}
