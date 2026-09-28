\
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(p): return json.loads((ROOT/p).read_text(encoding="utf-8"))

def test_release_candidate_identity_and_governance():
    c=load("MODEL3I_RELEASE_CANDIDATE.json")
    assert c["planned_release_tag"]=="model3-potential-output-v1.0.0"
    assert c["selected_candidate"]["candidate_id"]=="3D"
    assert c["release_status"]=="pre_commit_release_candidate"
    assert c["governance"]["econometric_retuning_allowed"] is False
    assert c["governance"]["post_hoc_revision_cutoff_allowed"] is False

def test_no_lookahead_evidence_is_frozen_pass():
    x=load("reports/model3i_release_audits/MODEL3I_NO_LOOKAHEAD_AUDIT.json")
    assert x["status"]=="PASS"
    assert x["complete_three_series_vintages"]==213
    assert x["safe_loader_failures"]==0
    assert all(v["future_rows"]==0 for v in x["required_series"].values())

def test_revision_diagnostic_does_not_reopen_selection():
    x=load("reports/model3i_release_audits/MODEL3I_FIXED_QUARTER_REVISION_AUDIT.json")
    assert x["status"]=="PASS"
    assert x["candidate_id"]=="3D"
    assert x["recursive_fits"]==46
    assert x["recursive_fit_failures"]==0
    assert x["release_blocker"] is False
    assert x["selection_reopened"] is False

def test_empirical_evidence_manifest_is_nonempty():
    x=load("reports/model3i_release_audits/MODEL3H_EVIDENCE_MANIFEST.json")
    assert x["status"]=="PASS"
    assert len(x["directories"])==2
    assert len(x["files"])>0
    assert all(len(v["sha256"])==64 for v in x["files"])

def test_real_data_smoke_is_deterministic_and_governed():
    x=load("reports/model3i_release_audits/MODEL3I_PRODUCTION_SMOKE_TEST.json")
    assert x["status"]=="PASS"
    assert x["future_dated_rows"]==0
    assert x["deterministic_repeated_fit"] is True
    assert len(x["export_sha256"])==64
    p=x["current_estimate"]["provenance"]
    assert p["selected_candidate"]=="3D"
    assert p["estimate_class"]=="production_current_endpoint"

def test_release_candidate_verifier_is_descendant_safe_and_freezes_predecessor_sources():
    text=(ROOT/"scripts/verify_model3i_release_candidate.py").read_text(encoding="utf-8")
    assert 'merge-base","--is-ancestor"' in text
    assert 'PRED+".."+head' in text
    assert 'head != PRED and not ancestor(PRED,head)' in text
    assert 'rev-list","-n","1",PRED_TAG' in text
