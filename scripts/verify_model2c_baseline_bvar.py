from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2B2_CLOSURE = "90f529f635eeaa554259287ffc8a79647c92f7ad"
EXPECTED_2C_CLOSURE = "b321e3f59ac7165cf71b1b3155712312b58af1a7"
EXPECTED_2C_CI_RUN = 33888716133
EXPECTED_DELTA = {
    "MODEL2C_BASELINE_BVAR_CONTRACT.json",
    "docs/MODEL2C_BASELINE_BVAR.md",
    "src/macropulse/bvar/model.py",
    "scripts/smoke_model2c_bvar.py",
    "scripts/verify_model2c_baseline_bvar.py",
    "scripts/verify_model2b2_origin_grid.py",
    "tests/test_model2c_baseline_bvar.py",
    "src/macropulse/models/baseline.py",
    ".github/workflows/model2-bvar-guard.yml",
}
FROZEN_CONTENT = EXPECTED_DELTA - {"scripts/verify_model2c_baseline_bvar.py", ".github/workflows/model2-bvar-guard.yml"}

def git(*args: str) -> str:
    c=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,text=True,check=True)
    return c.stdout.strip()

def names(output: str) -> set[str]:
    return {line.strip().replace("\\","/") for line in output.splitlines() if line.strip()}

def main() -> int:
    errors=[]
    try:
        if git("branch","--show-current") != EXPECTED_BRANCH: errors.append("Wrong branch.")
        for ancestor in (EXPECTED_2B2_CLOSURE,EXPECTED_2C_CLOSURE):
            r=subprocess.run(["git","merge-base","--is-ancestor",ancestor,"HEAD"],cwd=ROOT,capture_output=True,text=True)
            if r.returncode != 0: errors.append("HEAD does not descend from " + ancestor)
        closure_delta=names(git("diff","--name-only",EXPECTED_2B2_CLOSURE+".."+EXPECTED_2C_CLOSURE))
        bad=sorted(closure_delta-EXPECTED_DELTA); missing=sorted(EXPECTED_DELTA-closure_delta)
        if bad: errors.append("Unexpected frozen 2C paths: "+", ".join(bad))
        if missing: errors.append("Missing frozen 2C paths: "+", ".join(missing))
        for path in sorted(FROZEN_CONTENT):
            r=subprocess.run(["git","diff","--quiet",EXPECTED_2C_CLOSURE,"--",path],cwd=ROOT,capture_output=True,text=True)
            if r.returncode != 0: errors.append("Frozen 2C content changed: "+path)
        payload=json.loads(git("show",EXPECTED_2C_CLOSURE+":MODEL2C_BASELINE_BVAR_CONTRACT.json"))
        if payload.get("workstream") != "2C": errors.append("Wrong frozen 2C workstream.")
        if payload.get("production_authority") != "none": errors.append("2C production authority changed.")
        grid=payload.get("candidate_grid",{})
        if grid.get("lags") != [2,4]: errors.append("Frozen 2C lag grid changed.")
        if grid.get("overall_shrinkage") != [0.1,0.2,0.4]: errors.append("Frozen 2C shrinkage grid changed.")
        if grid.get("candidate_count") != 6: errors.append("Frozen 2C candidate count changed.")
        if grid.get("selection_in_2c") is not False: errors.append("Frozen 2C selection boundary changed.")
        if grid.get("ranking_in_2c") is not False: errors.append("Frozen 2C ranking boundary changed.")
        maintenance=payload.get("dependency_compatibility_maintenance",{})
        if maintenance.get("paths") != ["src/macropulse/models/baseline.py"]: errors.append("Frozen 2C compatibility path changed.")
        for key in ("model1_forecast_semantics_changed","model2_bvar_semantics_changed","frozen_release_tags_changed","production_authority_changed"):
            if maintenance.get(key) is not False: errors.append("Frozen 2C compatibility boundary changed: "+key)
        workflow=(ROOT/".github"/"workflows"/"model2-bvar-guard.yml").read_text(encoding="utf-8")
        for token in ("python scripts/verify_model2c_baseline_bvar.py","tests/test_model2c_baseline_bvar.py"):
            if token not in workflow: errors.append("Current CI lost frozen 2C gate: "+token)
    except Exception as exc:
        errors.append(str(exc))
    if errors:
        print("Model 2C frozen baseline BVAR verification: FAIL")
        for error in errors: print("- "+error)
        return 1
    print("Model 2C frozen baseline BVAR verification: PASS")
    print("2B.2 closure: "+EXPECTED_2B2_CLOSURE[:7])
    print("2C closure: "+EXPECTED_2C_CLOSURE[:7])
    print("2C closure CI run: "+str(EXPECTED_2C_CI_RUN))
    print("Frozen delta paths: 9")
    print("Descendant-safe verification: PASS")
    print("Six-candidate grid frozen: PASS")
    print("statsmodels compatibility maintenance frozen: PASS")
    print("Candidate selection/ranking: prohibited")
    print("Production authority: none")
    print("Next: Model 2D permitted on descendants")
    return 0

if __name__ == "__main__": raise SystemExit(main())
