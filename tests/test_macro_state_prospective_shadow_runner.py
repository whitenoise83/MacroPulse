from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pandas as pd


def _load_runner():
    path = Path("scripts") / "run_macro_state_prospective_shadow.py"
    spec = importlib.util.spec_from_file_location(
        "run_macro_state_prospective_shadow_script",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_prints_research_shadow_summary(
    monkeypatch,
    capsys,
) -> None:
    module = _load_runner()
    monkeypatch.setattr(module, "MacroRepository", lambda: object())
    monkeypatch.setattr(
        module,
        "run_macro_state_prospective_shadow",
        lambda repository, as_of: {
            "shadow_run_id": "shadow-1",
            "model_id": "US_MACRO_STATE_1D",
            "model_version": "0.3.8",
            "lifecycle_status": "development",
            "state_date": date(2026, 8, 31),
            "information_cutoff": date(2026, 8, 5),
            "target_expected_available_date": date(2026, 11, 29),
            "source_macro_state_run_id": "macro-run-1",
            "source_candidate_id": (
                "expanding_robust_z__policy__equal__sensitive__"
                "independent_normal"
            ),
            "predictions": pd.DataFrame(
                [
                    {
                        "benchmark_id": benchmark,
                        "predicted_family": "mixed",
                        "top1_probability": 0.4,
                        "top2_family": "benign_expansion",
                        "top2_probability": 0.2,
                        "entropy": 1.4,
                        "probability_vector_hash": benchmark[0] * 64,
                    }
                    for benchmark in ("source", "rolling_frequency")
                ]
            ),
            "dimensions": pd.DataFrame(
                [
                    {
                        "dimension": dimension,
                        "score": 0.1,
                        "lower_score": -0.2,
                        "upper_score": 0.4,
                        "label": "test",
                        "confidence": 75.0,
                        "source_information_cutoff": date(2026, 8, 5),
                    }
                    for dimension in ("growth", "inflation", "labour")
                ]
            ),
            "governance": {"status": "pass"},
            "information_set_hash": "i" * 64,
            "source_bundle_hash": "s" * 64,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_macro_state_prospective_shadow.py",
            "--as-of",
            "2026-08-05",
        ],
    )

    module.main()
    output = capsys.readouterr().out
    assert "prospective transition shadow prediction complete" in output
    assert "Shadow run ID: shadow-1" in output
    assert "promotion authority none" in output
