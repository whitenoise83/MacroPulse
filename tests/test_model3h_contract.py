import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def payload():
    return json.loads((ROOT/"MODEL3H_PSEUDO_REAL_TIME_EVALUATION_CONTRACT.json").read_text())

def test_exact_predecessor():
    assert payload()["predecessor"]=="86e58f9c7a1bcec8818c6233bc658675293ffed3"

def test_candidates_frozen_before_results():
    p=payload()
    assert p["candidate_set"]==["3D","3E_A","3E_B"]
    assert p["selection_policy"]["selection_permitted_in_bootstrap"] is False

def test_downstream_tuning_prohibited():
    p=payload()
    assert p["selection_policy"]["model4_downstream_performance_allowed"] is False
    assert p["selection_policy"]["model1d_validation_is_selection_gate"] is False

def test_no_production_side_effects():
    g=payload()["governance"]
    assert g["no_database_writes"] is True
    assert g["no_production_promotion"] is True
