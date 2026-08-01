from pathlib import Path


def test_operational_metadata_repair_is_packaged() -> None:
    root = Path(__file__).resolve().parents[1]
    repair = root / "src" / "macropulse" / "labour" / "validation_repair.py"
    script = root / "scripts" / "repair_labour_operational_validation_metadata.py"
    promotion = root / "src" / "macropulse" / "labour" / "promotion.py"
    operational = (
        root / "src" / "macropulse" / "labour" / "operational_validation.py"
    )
    assert repair.is_file()
    assert script.is_file()
    assert "legacy_shift" in repair.read_text(encoding="utf-8")
    assert "repair_operational_validation_metadata" in promotion.read_text(
        encoding="utf-8"
    )
    op_text = operational.read_text(encoding="utf-8")
    assert '"backtest_id",' in op_text
    assert "save_labour_validation_outputs" in op_text
