from __future__ import annotations

import json
from datetime import date
from pathlib import Path
import pytest
from macropulse.evaluation.decision import build_decision_intelligence_snapshot
from macropulse.evaluation.ledger import collect_governed_forecasts, load_phase3_boundary

def test_future_evaluation_date_fails_closed() -> None:
    with pytest.raises(ValueError, match="future"):
        collect_governed_forecasts(
            object(), as_of=date(2999, 1, 1), project_root=Path(".")
        )

def test_future_decision_snapshot_date_fails_closed() -> None:
    with pytest.raises(ValueError, match="future"):
        build_decision_intelligence_snapshot(
            object(), as_of=date(2999, 1, 1), project_root=Path(".")
        )

def test_boundary_mutation_permission_fails_closed(tmp_path: Path) -> None:
    payload = {
        "phase": "III",
        "phase3_may_mutate_governed_forecasts": True,
        "phase3_may_tune_model1d_on_prospective_outcomes": False,
    }
    (tmp_path / "PHASE3_BOUNDARY.json").write_text(json.dumps(payload),encoding="utf-8")
    with pytest.raises(ValueError, match="mutation boundary"):
        load_phase3_boundary(tmp_path)

def test_model1d_tuning_permission_fails_closed(tmp_path: Path) -> None:
    payload = {
        "phase": "III",
        "phase3_may_mutate_governed_forecasts": False,
        "phase3_may_tune_model1d_on_prospective_outcomes": True,
    }
    (tmp_path / "PHASE3_BOUNDARY.json").write_text(json.dumps(payload),encoding="utf-8")
    with pytest.raises(ValueError, match="Model 1D tuning boundary"):
        load_phase3_boundary(tmp_path)
