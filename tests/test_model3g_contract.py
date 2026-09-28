import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_contract_boundary():
    p=json.loads((ROOT/"MODEL3G_FORWARD_GAP_CONTRACT.json").read_text())
    assert p["predecessor_commit"]=="effb612f0d637a217fd00b563a8efafb69156983"
    assert p["model2_release_tag"]=="model2-bvar-v1.0.2"
    assert p["model2_access"]=="read_only"
    assert p["model2_refit_allowed"] is False
    assert p["forecast_horizons_quarters"]==[1,2,4,8]
    assert p["potential_process"]["potential_uncertainty_claimed"] is False
    assert p["strict_pseudo_realtime_evaluation"]=="deferred_to_3H"
    assert p["next_authorized_workstream"]=="3H"
