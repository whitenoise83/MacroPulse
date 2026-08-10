from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "refresh_phase3_outcome_snapshots.py"


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "phase3_outcome_snapshot_refresh",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_refresh_runner_is_explicit_source_ingestion_only() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "replace_historical_snapshot(" in text
    assert "get_observations_as_of(" in text
    assert "save_forecast" not in text
    assert "save_inflation_live" not in text
    assert "save_labour_live" not in text
    assert "macro_state" not in text.lower()
    assert "run_staged" not in text
    assert "run_live" not in text


def test_refresh_runner_defaults_to_no_forced_replacement() -> None:
    runner = load_runner()
    args = runner.build_parser().parse_args([])
    assert args.refresh is False
