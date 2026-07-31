from pathlib import Path


def test_freeze_assessment_script_is_packaged() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "generate_inflation_freeze_assessment.py"
    text = script.read_text(encoding="utf-8")
    assert "ready_for_model_owner_signoff" in text
    assert "candidate_policy" in text
    assert "governed_live_operational" in text
    assert "exp_weighted_q80" in text or "SELECTED_INTERVAL_METHOD" in text
