from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXPECTED="effb612f0d637a217fd00b563a8efafb69156983"
PATHS={
"MODEL3G_FORWARD_GAP_CONTRACT.json",
"docs/MODEL3G_FORWARD_GAP_CONTRACT.md",
"scripts/verify_model3g_forward_gap.py",
"src/macropulse/slack/forward_gap.py",
"tests/test_model3g_contract.py",
"tests/test_model3g_forward_gap.py",
}
p=json.loads((ROOT/"MODEL3G_FORWARD_GAP_CONTRACT.json").read_text())
assert p["predecessor_commit"]==EXPECTED
assert p["model2_release_tag"]=="model2-bvar-v1.0.2"
assert p["model2_access"]=="read_only"
assert p["model2_refit_allowed"] is False
assert p["model3_candidate_selection_allowed"] is False
assert p["database_writes_allowed"] is False
assert p["forecast_horizons_quarters"]==[1,2,4,8]
assert p["distribution"]["preserve_draws"] is True
# MODEL3G_DENSE_PATH_INTERFACE
dense=p["model2_dense_path_interface"]
assert dense["dense_horizons_quarters"]==list(range(1,9))
assert dense["model2_source_modified"] is False
assert dense["model2_refit_required"] is False
assert dense["dense_draw_hash_is_distinct_from_production_draw_hash"] is True
assert dense["report_horizons_quarters"]==[1,2,4,8]
assert p["potential_process"]["model2_may_redefine_historical_or_current_potential"] is False
assert p["potential_process"]["potential_uncertainty_claimed"] is False
assert p["scenarios"]["supported_as_probabilistic_density"] is False
assert p["strict_pseudo_realtime_evaluation"]=="deferred_to_3H"
assert p["next_authorized_workstream"]=="3H"
for rel in PATHS:
    assert (ROOT/rel).is_file(), rel
print("Model 3G forward-gap verification: PASS")
print("Model 3F predecessor: effb612")
print("Model 2 release: model2-bvar-v1.0.2 (read-only)")
print("Horizons: 1, 2, 4, 8")
print("Potential uncertainty: not claimed")
print("3E candidate selection: none")
print("Next authorized workstream: 3H")
