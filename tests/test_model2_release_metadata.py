from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/"MODEL2_RELEASE.json"
MANIFEST=ROOT/"MANIFEST_MODEL2_v1.0.0.txt"
SOURCE_CLOSURE="df1da2bcd54cf71277eb8bfe21f6c52caad1c302"
TAG="model2-bvar-v1.0.0"
SELECTED_ID="a69878bf644615c5"
EVIDENCE_HASH="2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7"

def load_release(): return json.loads(RELEASE.read_text(encoding="utf-8"))

def entries():
    out={}
    for raw in MANIFEST.read_text(encoding="utf-8").splitlines():
        line=raw.strip()
        if line and not line.startswith("#"):
            d,p=line.split("  ",1); out[p]=d
    return out

def test_release_identity():
    r=load_release()
    assert r["roadmap_phase"]=="II" and r["model"]=="2" and r["model_name"]=="Bayesian VAR"
    assert r["version"]=="1.0.0" and r["release_tag"]==TAG

def test_source_closure_and_ci_identity():
    s=load_release()["source_closure"]
    assert s["commit"]==SOURCE_CLOSURE
    assert s["ci"]["run_number"]==13
    assert s["ci"]["run_id"]==35769859027
    assert s["ci"]["job_id"]==106888547394
    assert s["ci"]["head_sha"]==SOURCE_CLOSURE
    assert s["ci"]["conclusion"]=="success"

def test_selected_specification_is_frozen():
    s=load_release()["selected_specification"]
    assert s["candidate_id"]==SELECTED_ID and s["lags"]==2 and s["shrinkage"]==0.1
    assert s["selection_evidence_payload_hash"]==EVIDENCE_HASH

def test_manifest_hash_matches_release_record():
    r=load_release()
    assert r["manifest_sha256"]==hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert r["manifest_file_count"]==len(entries())

def test_manifest_hashes_source_closure_blobs():
    for p,d in entries().items():
        c=subprocess.run(["git","show",SOURCE_CLOSURE+":"+p],cwd=ROOT,capture_output=True,check=True)
        assert hashlib.sha256(c.stdout).hexdigest()==d

def test_release_governance_is_fail_closed():
    g=load_release()["governance"]
    for k in ("candidate_specification_immutable","prospective_retuning_prohibited","automatic_switching_prohibited","model1d_prospective_outcomes_excluded","historical_model1_backfill_prohibited","generative_ai_in_governed_core_prohibited"):
        assert g[k] is True

def test_release_execution_authority_is_limited():
    a=load_release()["execution_authority"]
    assert a["core_forecast_interface"]=="authorized_when_tag_verified"
    for k in ("automatic_model_switching","automatic_candidate_reselection","database_write_authority","scenario_probability_authority","unidentified_causal_claim_authority"):
        assert a[k]=="none"

def test_release_verifier_is_tag_optional_before_tag_creation():
    c=subprocess.run(["python","scripts/verify_model2_release.py","--skip-prerequisite-verifiers"],cwd=ROOT,capture_output=True,text=True)
    assert c.returncode==0, c.stdout+c.stderr
