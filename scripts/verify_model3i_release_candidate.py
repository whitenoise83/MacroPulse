\
from __future__ import annotations
import json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PRED="a8ebf2d05a3b49d0c21f5ab1b03ca6eefca0b094"
PRED_TAG="model3-pseudo-real-time-v1.0.0"
PLANNED="model3-potential-output-v1.0.0"

def git(*args):
    c=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,text=True)
    if c.returncode:
        raise RuntimeError("git "+" ".join(args)+" failed:\n"+c.stdout+c.stderr)
    return c.stdout.strip()

def ancestor(older: str, newer: str) -> bool:
    c=subprocess.run(
        ["git","merge-base","--is-ancestor",older,newer],
        cwd=ROOT,capture_output=True,text=True
    )
    return c.returncode==0

def load(path):
    return json.loads((ROOT/path).read_text(encoding="utf-8"))

errors=[]
try:
    head=git("rev-parse","HEAD")
    if git("rev-list","-n","1",PRED_TAG) != PRED:
        errors.append("Immutable Model 3H predecessor tag moved.")

    # Valid in both bootstrap/pre-commit state (HEAD == predecessor) and
    # source-hardening/CI state (HEAD is a descendant of predecessor).
    if head != PRED and not ancestor(PRED,head):
        errors.append("Current HEAD is not descended from frozen Model 3H predecessor.")

    c=load("MODEL3I_RELEASE_CANDIDATE.json")
    if c.get("planned_release_tag") != PLANNED: errors.append("Planned release tag mismatch.")
    if c.get("selected_candidate",{}).get("candidate_id") != "3D": errors.append("Selected candidate is not 3D.")
    if c.get("release_status") != "pre_commit_release_candidate": errors.append("Candidate status changed.")
    g=c.get("governance",{})
    for key in ("econometric_retuning_allowed","model1_mutation_allowed","model2_mutation_allowed",
                "model3_predecessor_mutation_allowed","model4_performance_selection_allowed",
                "post_hoc_revision_cutoff_allowed"):
        if g.get(key) is not False: errors.append("Governance gate changed: "+key)

    n=load("reports/model3i_release_audits/MODEL3I_NO_LOOKAHEAD_AUDIT.json")
    if n.get("status")!="PASS" or n.get("complete_three_series_vintages")!=213:
        errors.append("No-lookahead audit record invalid.")
    if any(v.get("future_rows")!=0 for v in n.get("required_series",{}).values()):
        errors.append("No-lookahead record contains future rows.")
    if n.get("safe_loader_failures")!=0: errors.append("Safe-loader failures recorded.")

    r=load("reports/model3i_release_audits/MODEL3I_FIXED_QUARTER_REVISION_AUDIT.json")
    if r.get("status")!="PASS" or r.get("candidate_id")!="3D": errors.append("Revision audit invalid.")
    if r.get("release_blocker") is not False or r.get("selection_reopened") is not False:
        errors.append("Revision audit governance changed.")
    if r.get("recursive_fits")!=46 or r.get("recursive_fit_failures")!=0:
        errors.append("Revision recursive-fit evidence changed.")

    m=load("reports/model3i_release_audits/MODEL3H_EVIDENCE_MANIFEST.json")
    if m.get("status")!="PASS" or not m.get("files"): errors.append("Model3H evidence manifest invalid.")
    if len(m.get("directories",[]))!=2: errors.append("Expected two Model3H evidence directories.")

    s=load("reports/model3i_release_audits/MODEL3I_PRODUCTION_SMOKE_TEST.json")
    if s.get("status")!="PASS" or s.get("release_status")!="pre_tag_validation":
        errors.append("Production smoke record invalid.")
    if s.get("planned_release_tag")!=PLANNED: errors.append("Smoke release identity mismatch.")
    if s.get("future_dated_rows")!=0 or s.get("deterministic_repeated_fit") is not True:
        errors.append("Production smoke determinism/no-lookahead failed.")
    prov=s.get("current_estimate",{}).get("provenance",{})
    if prov.get("selected_candidate")!="3D": errors.append("Smoke candidate is not 3D.")
    if prov.get("estimate_class")!="production_current_endpoint": errors.append("Smoke estimate class invalid.")

    req=(ROOT/"requirements.txt").read_text(encoding="utf-8")
    py=(ROOT/"pyproject.toml").read_text(encoding="utf-8")
    dep="statsmodels>=0.14.6,<0.16"
    if dep not in req or f'"{dep}"' not in py:
        errors.append("statsmodels dependency normalization missing.")

    frozen=[
      "src/macropulse/slack/state_space.py",
      "src/macropulse/slack/forward_gap.py",
      "src/macropulse/slack/evaluation.py",
      "src/macropulse/bvar/data.py",
    ]
    # Protect both committed ancestry and local working tree.
    if head != PRED and git("diff","--name-only",PRED+".."+head,"--",*frozen):
        errors.append("Frozen predecessor/Model2 source changed in Model 3I descendant commit.")
    if git("diff","--name-only","HEAD","--",*frozen):
        errors.append("Frozen predecessor/Model2 source has local working-tree changes.")
except Exception as exc:
    errors.append(str(exc))

if errors:
    print("Model 3I release-candidate verification: FAIL")
    for e in errors: print("- "+e)
    raise SystemExit(1)

print("Model 3I release-candidate verification: PASS")
print("Predecessor:",PRED[:7])
print("HEAD:",git("rev-parse","--short","HEAD"))
print("Lineage: predecessor retained / descendant-safe")
print("Selected candidate: 3D")
print("No-lookahead audit: PASS")
print("Fixed-quarter revision robustness: PASS / no selection reopening")
print("3H empirical evidence manifest: PASS")
print("Real-data deterministic production smoke: PASS")
print("Planned final tag:",PLANNED)
print("Production promotion: NO - branch CI/tag gates still pending")
