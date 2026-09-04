from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"MODEL2D_PROBABILISTIC_FORECAST_CONTRACT.json"
EXPECTED_BRANCH="model2-bvar-development"
EXPECTED_2C_CLOSURE="b321e3f59ac7165cf71b1b3155712312b58af1a7"
EXPECTED_DELTA={
    "MODEL2D_PROBABILISTIC_FORECAST_CONTRACT.json",
    "docs/MODEL2D_PROBABILISTIC_FORECASTS.md",
    "src/macropulse/bvar/probabilistic.py",
    "scripts/smoke_model2d_probabilistic.py",
    "scripts/verify_model2d_probabilistic.py",
    "scripts/verify_model2c_baseline_bvar.py",
    "tests/test_model2d_probabilistic.py",
    ".github/workflows/model2-bvar-guard.yml",
}
IGNORED_PREFIXES=("src/macropulse.egg-info/","reports/inflation_operational_validation/","reports/labour_operational_validation/")

def git(*args:str)->str:
    c=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,text=True,check=True); return c.stdout.strip()

def names(output:str)->set[str]:
    return {line.strip().replace("\\","/") for line in output.splitlines() if line.strip()}

def ignorable(path:str)->bool:
    normalized=path.replace("\\","/"); return any(normalized.startswith(prefix) for prefix in IGNORED_PREFIXES)

def main()->int:
    errors=[]
    try:
        if git("branch","--show-current") != EXPECTED_BRANCH: errors.append("Wrong branch.")
        ancestor=subprocess.run(["git","merge-base","--is-ancestor",EXPECTED_2C_CLOSURE,"HEAD"],cwd=ROOT,capture_output=True,text=True)
        if ancestor.returncode != 0: errors.append("HEAD does not descend from closed Model 2C.")
        committed=names(git("diff","--name-only",EXPECTED_2C_CLOSURE+"..HEAD"))
        working={p for p in names(git("diff","--name-only")) if not ignorable(p)}
        staged=names(git("diff","--cached","--name-only"))
        untracked={p for p in names(git("ls-files","--others","--exclude-standard")) if not ignorable(p)}
        observed=committed|working|staged|untracked
        bad=sorted(observed-EXPECTED_DELTA); missing=sorted(EXPECTED_DELTA-observed)
        if bad: errors.append("Unexpected 2D paths: "+", ".join(bad))
        if missing: errors.append("Missing 2D paths: "+", ".join(missing))
        payload=json.loads(CONTRACT.read_text(encoding="utf-8"))
        if payload.get("workstream") != "2D": errors.append("Wrong workstream identity.")
        if payload.get("base_model2c_closure_commit") != EXPECTED_2C_CLOSURE: errors.append("Wrong 2C closure base.")
        if payload.get("production_authority") != "none": errors.append("Production authority must remain none.")
        policy=payload.get("candidate_policy",{})
        if policy.get("all_six_model2c_candidates_retained") is not True: errors.append("2D candidate retention changed.")
        for key in ("candidate_selection_in_2d","candidate_ranking_in_2d","automatic_candidate_exclusion_in_2d"):
            if policy.get(key) is not False: errors.append("2D candidate action changed: "+key)
        predictive=payload.get("posterior_predictive",{})
        for key in ("future_innovations_drawn","one_parameter_draw_per_simulated_path","parameter_uncertainty_included","innovation_uncertainty_included","recursive_multi_step_simulation"):
            if predictive.get(key) is not True: errors.append("2D predictive rule changed: "+key)
        if predictive.get("stability_truncation_or_rejection") is not False: errors.append("2D stability truncation boundary changed.")
        simulation=payload.get("simulation",{})
        if simulation.get("canonical_default_seed") != 20260904: errors.append("2D default seed changed.")
        if simulation.get("canonical_default_simulations") != 5000: errors.append("2D default simulation count changed.")
        if simulation.get("minimum_simulations") != 100: errors.append("2D minimum simulation count changed.")
        forecast=payload.get("forecast",{})
        if forecast.get("horizons_quarters") != [1,2,4,8]: errors.append("2D forecast horizons changed.")
        if forecast.get("central_interval_coverage") != [0.5,0.8,0.95]: errors.append("2D interval coverage changed.")
        governance=payload.get("governance",{})
        for key in ("no_candidate_selection","no_candidate_ranking","no_estimation_start_selection","no_evaluation_start_selection","no_model1_historical_backfill","no_model1d_prospective_outcomes","no_frozen_release_changes","no_production_promotion"):
            if governance.get(key) is not True: errors.append("2D governance changed: "+key)
        workflow=(ROOT/".github"/"workflows"/"model2-bvar-guard.yml").read_text(encoding="utf-8")
        for token in ("python scripts/verify_model2d_probabilistic.py","tests/test_model2d_probabilistic.py"):
            if token not in workflow: errors.append("Model 2 CI missing 2D gate: "+token)
    except Exception as exc:
        errors.append(str(exc))
    if errors:
        print("Model 2D probabilistic forecast verification: FAIL")
        for error in errors: print("- "+error)
        return 1
    print("Model 2D probabilistic forecast verification: PASS")
    print("Base 2C closure: "+EXPECTED_2C_CLOSURE[:7])
    print("Expected delta paths: 8")
    print("Six Model 2C candidates retained: PASS")
    print("Posterior parameter uncertainty: included")
    print("Future innovation uncertainty: included")
    print("Central intervals: 50%, 80%, 95%")
    print("Default seed: 20260904")
    print("Default simulations: 5000")
    print("Candidate selection/ranking in 2D: prohibited")
    print("Calibration/density evaluation: deferred to 2G")
    print("Scenario conditioning: deferred to 2F")
    print("Production authority: none")
    return 0

if __name__ == "__main__": raise SystemExit(main())
