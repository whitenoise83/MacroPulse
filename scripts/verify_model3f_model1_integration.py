from __future__ import annotations
import json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDECESSOR = "5378dd8aeef716f17e46f73716803ac20d101516"
BRANCH = "model3-output-gap-development"
EXPECTED = {
    "MODEL3F_MODEL1_INTEGRATION_CONTRACT.json",
    "docs/MODEL3F_MODEL1_INTEGRATION_CONTRACT.md",
    "scripts/verify_model3f_model1_integration.py",
    "src/macropulse/slack/model1_integration.py",
    "tests/test_model3f_contract.py",
    "tests/test_model3f_model1_integration.py",
}
IGNORED = ("reports/inflation_operational_validation/", "reports/labour_operational_validation/")

def git(*args): return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
def fail(msg): raise SystemExit("Model 3F Model 1 integration verification: FAIL\n" + msg)

def main():
    if git("rev-parse", "--abbrev-ref", "HEAD") not in {BRANCH, "HEAD"}: fail("wrong branch")
    if git("merge-base", PREDECESSOR, "HEAD") != PREDECESSOR: fail("HEAD is not descendant of exact frozen 3E predecessor")
    contract = json.loads((ROOT / "MODEL3F_MODEL1_INTEGRATION_CONTRACT.json").read_text(encoding="utf-8"))
    if contract["model3e_predecessor_commit"] != PREDECESSOR: fail("predecessor mismatch")
    if contract["inputs"]["model1_read_only"] is not True: fail("Model 1 must be read-only")
    if contract["inputs"]["model1_refit_allowed"] or contract["inputs"]["model1_mutation_allowed"]: fail("Model 1 mutation/refit forbidden")
    if contract["inputs"]["model2_forecasts_allowed"]: fail("Model 2 belongs to 3G")
    if contract["inputs"]["model3e_candidate_selection_allowed"]: fail("candidate selection belongs to 3H")
    if contract["governance"]["database_writes_allowed"]: fail("DB writes forbidden")
    status = git("status", "--porcelain").splitlines()
    paths=[]
    for line in status:
        p=line[3:].replace("\\", "/")
        if p.startswith(IGNORED): continue
        paths.append(p)
    if set(paths) != EXPECTED: fail(f"3F delta is not exactly six governed paths: {paths}")
    print("Model 3F Model 1 integration verification: PASS")
    print("Model 3E predecessor: 5378dd8")
    print("3F delta paths: 6")
    print("Model 1 access: read-only; provenance preserving")
    print("3E candidate selection: none")
    print("Model 2 consumption: none")
    print("Next authorized workstream: 3G Model 2 forward-gap integration")
if __name__ == "__main__": main()
