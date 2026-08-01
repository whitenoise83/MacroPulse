from pathlib import Path


def test_model1c_promotion_tooling_is_packaged() -> None:
    root = Path(__file__).resolve().parents[1]
    module = root / "src" / "macropulse" / "labour" / "promotion.py"
    script = root / "scripts" / "promote_model1c_v1.py"
    assert module.is_file()
    assert script.is_file()
    text = module.read_text(encoding="utf-8")
    assert "EXPECTED_CANDIDATE_PASSES = 39" in text
    assert "EXPECTED_OPERATIONAL_PASSES = 20" in text
    assert "EXPECTED_FREEZE_PASSES = 14" in text
    assert "APPROVE MODEL 1C FREEZE" in text
