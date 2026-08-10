from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "report_forecast_revisions.py"


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "phase3_revision_runner",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_runner_defaults_to_read_only_text_mode() -> None:
    runner = load_runner()
    args = runner.build_parser().parse_args([])
    assert args.json is False
    assert args.events is False
    assert args.component is None
    assert args.target_series is None


def test_runner_contains_no_write_download_or_model_execution_control() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    forbidden = [
        "--execute",
        "--refresh",
        "--download",
        "initialise(",
        "save_forecast",
        "replace_historical_snapshot",
        "run_staged",
        "run_live",
        "macro_state",
    ]
    for token in forbidden:
        assert token not in text
