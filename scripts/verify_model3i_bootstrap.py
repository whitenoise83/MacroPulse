from pathlib import Path
import json, subprocess

ROOT=Path(__file__).resolve().parents[1]
EXPECTED="a8ebf2d05a3b49d0c21f5ab1b03ca6eefca0b094"
TAG="model3-pseudo-real-time-v1.0.0"
head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
assert head==EXPECTED, f"Expected 3H boundary {EXPECTED}, got {head}"
tag=subprocess.check_output(["git","rev-list","-n","1",TAG],cwd=ROOT,text=True).strip()
assert tag==EXPECTED, f"{TAG} does not resolve to governed predecessor"

c=json.loads((ROOT/"MODEL3I_PRODUCTION_HARDENING_CONTRACT.json").read_text())
s=json.loads((ROOT/"reports/model3h_selection/MODEL3H_SELECTION_DECISION.json").read_text())
assert c["predecessor_commit"]==EXPECTED
assert c["predecessor_tag"]==TAG
assert c["selected_candidate"]=="3D"
assert s["selected_candidate"]=="3D" and s["production_promotion"] is False
assert c["production_promotion_in_bootstrap"] is False
assert c["database_writes_in_bootstrap"] is False
assert c["econometric_retuning_allowed"] is False
assert c["dependency_policy"]["requirements_statsmodels"]=="statsmodels>=0.14.6,<0.16"
assert c["release_tag_planned"]=="model3-potential-output-v1.0.0"
print("Model 3I bootstrap verification: PASS")
print("Predecessor:", head[:7])
print("Frozen tag:", TAG)
print("Selected candidate: 3D")
print("Production promotion: NO")
print("Planned final tag: model3-potential-output-v1.0.0")
