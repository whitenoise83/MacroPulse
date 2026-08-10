from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "report_forecast_evaluation.py"


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "phase3_evaluation_runner",
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
    assert args.component is None
    assert args.show == 20


def test_runner_has_no_write_or_refresh_switch() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "--execute" not in text
    assert "--refresh" not in text
    assert "--download" not in text
    assert "initialise(" not in text
    assert "save_" not in text
