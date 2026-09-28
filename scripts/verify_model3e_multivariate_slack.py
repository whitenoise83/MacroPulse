import json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[1]; D="4a33072b8c2d767fb4eecdf6efc1aba879373ff2"
E={"MODEL3E_MULTIVARIATE_SLACK_CONTRACT.json","docs/MODEL3E_MULTIVARIATE_SLACK_CONTRACT.md","scripts/verify_model3e_multivariate_slack.py","src/macropulse/slack/multivariate.py","tests/test_model3e_contract.py","tests/test_model3e_multivariate.py"}
IGN=("reports/inflation_operational_validation/","reports/labour_operational_validation/","reports/decision_intelligence_snapshots/","data/backups/","src/macropulse.egg-info/")
def g(*a): return subprocess.check_output(["git",*a],cwd=R,text=True).strip()
def fail(x): raise SystemExit("Model 3E multivariate slack verification: FAIL\n"+x)
if g("merge-base",D,"HEAD")!=D: fail("Wrong Model 3D predecessor.")
tracked={x for x in g("diff","--name-only",D,"HEAD").splitlines() if x}
untracked={x for x in g("ls-files","--others","--exclude-standard").splitlines() if x and not x.startswith(IGN)}
if tracked|untracked!=E: fail("3E delta is not exactly six governed paths: "+repr(sorted(tracked|untracked)))
c=json.loads((R/"MODEL3E_MULTIVARIATE_SLACK_CONTRACT.json").read_text())
if c["model3d_base_commit"]!=D or c["inherited_gdp_state_system"]["sigma_potential_fixed"]!=0: fail("3D identification mismatch.")
if set(c["candidates"])!={"3E_A","3E_B"} or c["candidates"]["3E_B"]["stochastic_nairu_allowed"] is not False: fail("Candidate contract mismatch.")
if c["selection"]["pseudo_real_time_selection_deferred_to"]!="3H" or c["bootstrap"]["passing_3e_authorizes_only"]!="3F_model1_current_state_integration": fail("Governance sequencing mismatch.")
print("Model 3E multivariate slack verification: PASS")
print("Model 3D corrected predecessor: 4a33072"); print("3E delta paths: 6"); print("Candidates: 3E_A inflation; 3E_B inflation + unemployment"); print("Production winner: none"); print("Next authorized workstream: 3F")
