from pathlib import Path
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]
EXPECTED="86e58f9c7a1bcec8818c6233bc658675293ffed3"
PATHS={
"MODEL3H_PSEUDO_REAL_TIME_EVALUATION_CONTRACT.json",
"docs/MODEL3H_PSEUDO_REAL_TIME_EVALUATION_CONTRACT.md",
"scripts/verify_model3h_pseudo_real_time.py",
"src/macropulse/slack/evaluation.py",
"tests/test_model3h_contract.py",
"tests/test_model3h_evaluation.py",
}
p=json.loads((ROOT/"MODEL3H_PSEUDO_REAL_TIME_EVALUATION_CONTRACT.json").read_text())
assert p["predecessor"]==EXPECTED
assert p["candidate_set"]==["3D","3E_A","3E_B"]
assert p["estimate_label"]=="filtered_real_time_endpoint"
assert p["selection_policy"]["selection_permitted_in_bootstrap"] is False
assert p["selection_policy"]["weighted_composite_score"] is False
assert p["selection_policy"]["model4_downstream_performance_allowed"] is False
assert p["selection_policy"]["model1d_validation_is_selection_gate"] is False
assert p["governance"]["no_database_writes"] is True
assert p["governance"]["no_production_promotion"] is True
# RECURSIVE_ENGINE_GUARD
engine=p["recursive_engine"]
assert engine["candidate_refit_each_origin"] is True
assert engine["endpoint_relabel"]=="filtered_real_time_endpoint"
assert engine["smoothed_path_used_for_realtime_endpoint"] is False
assert engine["candidate_failure_policy"]=="record failure and continue other candidates/origins"
head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
assert head==EXPECTED, f"Expected predecessor {EXPECTED}, got {head}"
status=subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True)
new={line[3:].replace("\\","/") for line in status.splitlines() if line.startswith("?? ")}
delta={x for x in new if x.startswith(("MODEL3H_","docs/MODEL3H_","scripts/verify_model3h_","src/macropulse/slack/evaluation.py","tests/test_model3h_"))}
assert delta==PATHS, f"Unexpected 3H bootstrap delta: {sorted(delta)}"
print("Model 3H bootstrap verification: PASS")
print("Predecessor:",EXPECTED[:7])
print("Candidates: 3D, 3E-A, 3E-B")
print("Selection in bootstrap: NONE")
print("Estimate label: filtered_real_time_endpoint")
print("Next after governed 3H evaluation: 3I")
