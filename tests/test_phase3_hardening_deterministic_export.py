from __future__ import annotations

from pathlib import Path
from macropulse.evaluation.decision import write_decision_intelligence_snapshot

def snapshot() -> dict:
    return {
        "snapshot_schema_version": "1.0.0",
        "as_of": "2026-08-10",
        "contract": {"database_access": "read_only", "model_execution": "none",
                     "automatic_model_action": "none"},
        "summary": {"current_target_count": 8, "resolved_evaluation_rows": 4},
        "current_forecasts": [], "evidence_flags": [], "evaluation": {},
        "performance": {}, "revisions": {}, "freshness": {}, "calendar": {},
        "provenance": {},
        "model1d_research": {
            "separation": "research_only_no_production_evaluation_authority"
        },
        "snapshot_hash": "fixture-hash",
    }

def test_identical_snapshot_exports_are_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "a" / "snapshot.json"
    second = tmp_path / "b" / "snapshot.json"
    write_decision_intelligence_snapshot(snapshot(), first)
    write_decision_intelligence_snapshot(snapshot(), second)
    assert first.read_bytes() == second.read_bytes()

def test_export_path_is_not_serialised_into_snapshot(tmp_path: Path) -> None:
    output = tmp_path / "arbitrary-name.json"
    write_decision_intelligence_snapshot(snapshot(), output)
    text = output.read_text(encoding="utf-8")
    assert str(output) not in text
    assert "fixture-hash" in text
