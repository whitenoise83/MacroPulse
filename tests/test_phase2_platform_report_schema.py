from __future__ import annotations

import json
from pathlib import Path

from macropulse.platform.snapshot import SNAPSHOT_SCHEMA_VERSION


ROOT = Path(__file__).parents[1]
CONTRACT = ROOT / "PHASE2_PLATFORM_CONTRACT.json"


def test_snapshot_schema_version_is_pinned() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert payload["snapshot_schema"]["version"] == SNAPSHOT_SCHEMA_VERSION
    assert SNAPSHOT_SCHEMA_VERSION == "1.0.0"


def test_snapshot_contract_requires_governed_core_sections() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    required = set(payload["snapshot_schema"]["required_top_level_keys"])
    assert {
        "readiness",
        "production",
        "changes_since_previous_governed_run",
        "model1d",
        "freshness",
        "calendar",
        "provenance",
        "snapshot_hash",
    }.issubset(required)


def test_readiness_schema_uses_valid_not_current_semantics() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    readiness = set(payload["snapshot_schema"]["required_readiness_keys"])
    assert "model1d_shadow_valid" in readiness
    assert "model1d_shadow_current" not in readiness


def test_snapshot_requires_all_production_components() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert payload["snapshot_schema"]["required_production_components"] == [
        "1A",
        "1B",
        "1C",
    ]
