from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILE = ROOT / "MODEL2_RELEASE.json"
MANIFEST_FILE = ROOT / "MANIFEST_MODEL2_v1.0.0.txt"
TAG = "model2-bvar-v1.0.0"
BASE_PHASE3 = "edfc37b8f5f016710fb96402d205dcd35f2e09ca"
SOURCE_CLOSURE = "df1da2bcd54cf71277eb8bfe21f6c52caad1c302"
SOURCE_CI_RUN = 35769859027
SOURCE_CI_JOB = 106888547394
SOURCE_CI_NUMBER = 13
SELECTED_ID = "a69878bf644615c5"
EVIDENCE_HASH = "2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7"
RELEASE_PATCH_PATHS = {
    ".github/workflows/model2-bvar-guard.yml",
    "MODEL2_RELEASE.json",
    "MANIFEST_MODEL2_v1.0.0.txt",
    "README_MODEL2_v1.0.0.md",
    "VALIDATION_MODEL2_v1.0.0.txt",
    "scripts/verify_model2h_production.py",
    "scripts/verify_model2_release.py",
    "tests/test_model2_release_metadata.py",
}
IGNORED_PREFIXES = (
    "src/macropulse.egg-info/",
    "reports/inflation_operational_validation/",
    "reports/labour_operational_validation/",
)

def git(*args: str, binary: bool=False):
    c = subprocess.run(["git",*args], cwd=ROOT, capture_output=True, text=not binary)
    if c.returncode:
        out = c.stdout.decode(errors="replace") if binary else c.stdout
        err = c.stderr.decode(errors="replace") if binary else c.stderr
        raise RuntimeError("git "+" ".join(args)+" failed:\n"+out+err)
    return c.stdout

def gt(*args: str) -> str:
    return str(git(*args)).strip()

def names(output: str) -> set[str]:
    return {x.strip().replace("\\","/") for x in output.splitlines() if x.strip()}

def ignorable(path: str) -> bool:
    p=path.replace("\\","/")
    return any(p.startswith(x) for x in IGNORED_PREFIXES)

def blob(path: str, ref: str) -> bytes:
    return bytes(git("show",ref+":"+path,binary=True))

def load_manifest() -> dict[str,str]:
    out={}
    for raw in MANIFEST_FILE.read_text(encoding="utf-8").splitlines():
        line=raw.strip()
        if line and not line.startswith("#"):
            d,p=line.split("  ",1); out[p]=d
    return out

def source_paths() -> set[str]:
    return names(gt("diff","--diff-filter=ACMRT","--name-only",BASE_PHASE3+".."+SOURCE_CLOSURE))

def observed_patch() -> set[str]:
    committed=names(gt("diff","--name-only",SOURCE_CLOSURE+"..HEAD"))
    working={p for p in names(gt("diff","--name-only")) if not ignorable(p)}
    staged=names(gt("diff","--cached","--name-only"))
    untracked={p for p in names(gt("ls-files","--others","--exclude-standard")) if not ignorable(p)}
    return committed|working|staged|untracked

def verify_release_record(release: dict, manifest: dict[str,str]) -> list[str]:
    e=[]
    expected={"roadmap_phase":"II","model":"2","model_name":"Bayesian VAR","version":"1.0.0","release_tag":TAG,"release_branch":"model2-bvar-development","release_record_type":"immutable_tag_release"}
    for k,v in expected.items():
        if release.get(k)!=v: e.append("Release record mismatch for "+k)
    source=release.get("source_closure",{})
    if source.get("commit")!=SOURCE_CLOSURE: e.append("Source closure changed.")
    ci=source.get("ci",{})
    checks={"workflow":"Model 2 Bayesian VAR Guard","run_number":SOURCE_CI_NUMBER,"run_id":SOURCE_CI_RUN,"job_id":SOURCE_CI_JOB,"status":"completed","conclusion":"success","head_sha":SOURCE_CLOSURE}
    for k,v in checks.items():
        if ci.get(k)!=v: e.append("Source CI mismatch for "+k)
    s=release.get("selected_specification",{})
    if s.get("candidate_id")!=SELECTED_ID or s.get("lags")!=2 or abs(float(s.get("shrinkage",-1))-0.1)>1e-12:
        e.append("Released selected specification changed.")
    if s.get("selection_evidence_payload_hash")!=EVIDENCE_HASH: e.append("Selection evidence identity changed.")
    g=release.get("governance",{})
    for k in ("candidate_specification_immutable","prospective_retuning_prohibited","automatic_switching_prohibited","model1d_prospective_outcomes_excluded","historical_model1_backfill_prohibited","generative_ai_in_governed_core_prohibited"):
        if g.get(k) is not True: e.append("Release governance changed: "+k)
    if release.get("manifest_file")!=MANIFEST_FILE.name: e.append("Manifest filename changed.")
    if release.get("manifest_file_count")!=len(manifest): e.append("Manifest file count changed.")
    if release.get("manifest_sha256")!=hashlib.sha256(MANIFEST_FILE.read_bytes()).hexdigest(): e.append("Manifest SHA-256 changed.")
    a=release.get("execution_authority",{})
    if a.get("core_forecast_interface")!="authorized_when_tag_verified": e.append("Forecast authority boundary changed.")
    for k in ("automatic_model_switching","automatic_candidate_reselection","database_write_authority","scenario_probability_authority","unidentified_causal_claim_authority"):
        if a.get(k)!="none": e.append("Execution authority changed: "+k)
    return e

def verify_manifest(m: dict[str,str]) -> list[str]:
    e=[]
    expected=source_paths()
    if set(m)!=expected:
        miss=sorted(expected-set(m)); extra=sorted(set(m)-expected)
        if miss: e.append("Manifest missing: "+", ".join(miss))
        if extra: e.append("Manifest extra: "+", ".join(extra))
    for p,d in m.items():
        if hashlib.sha256(blob(p,SOURCE_CLOSURE)).hexdigest()!=d:
            e.append("Manifest checksum mismatch: "+p)
    return e

def verify_identity() -> list[str]:
    e=[]
    for ancestor,desc,label in ((BASE_PHASE3,SOURCE_CLOSURE,"Phase III -> Model 2"),(SOURCE_CLOSURE,"HEAD","source closure -> current")):
        c=subprocess.run(["git","merge-base","--is-ancestor",ancestor,desc],cwd=ROOT)
        if c.returncode: e.append("Lineage failure: "+label)
    o=observed_patch()
    if o!=RELEASE_PATCH_PATHS:
        extra=sorted(o-RELEASE_PATCH_PATHS); miss=sorted(RELEASE_PATCH_PATHS-o)
        if extra: e.append("Unexpected release-patch paths: "+", ".join(extra))
        if miss: e.append("Missing release-patch paths: "+", ".join(miss))
    return e

def verify_prerequisites() -> list[str]:
    e=[]
    cmds=(
        ["python","scripts/verify_phase2_release.py","--require-tag"],
        ["python","scripts/verify_model1d_v038_release.py","--require-tags"],
        ["python","scripts/verify_phase3_release.py","--require-tag"],
        ["python","scripts/verify_model2g_evaluation.py"],
        ["python","scripts/verify_model2h_production.py"],
    )
    for cmd in cmds:
        c=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        if c.returncode: e.append("Prerequisite failed: "+" ".join(cmd)+"\n"+c.stdout+c.stderr)
    return e

def verify_runtime() -> list[str]:
    bad=[]
    for raw in gt("ls-files").splitlines():
        p=raw.replace("\\","/").lower()
        if p.startswith("data/backups/") or p.endswith(".duckdb") or p.endswith(".wal") or p.startswith("reports/decision_intelligence_snapshots/"):
            bad.append(raw)
    return [] if not bad else ["Tracked runtime artifacts: "+", ".join(bad)]

def verify_tag(require: bool) -> list[str]:
    present=gt("tag","--list",TAG)
    if not present: return ["Required Model 2 release tag is missing: "+TAG] if require else []
    target=gt("rev-parse",TAG+"^{commit}")
    head=gt("rev-parse","HEAD")
    return [] if target==head else ["Model 2 release tag does not point to current release commit."]

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--require-tag",action="store_true")
    ap.add_argument("--skip-prerequisite-verifiers",action="store_true")
    args=ap.parse_args()
    errors=[]
    try:
        manifest=load_manifest()
        release=json.loads(RELEASE_FILE.read_text(encoding="utf-8"))
        errors+=verify_release_record(release,manifest)
        errors+=verify_manifest(manifest)
        errors+=verify_identity()
        errors+=verify_runtime()
        errors+=verify_tag(args.require_tag)
        if not args.skip_prerequisite_verifiers: errors+=verify_prerequisites()
    except Exception as exc:
        errors.append(str(exc))
    if errors:
        print("Model 2 BVAR v1.0.0 release verification: FAIL")
        for x in errors: print("- "+x)
        return 1
    print("Model 2 BVAR v1.0.0 release verification: PASS")
    print("Source closure: "+SOURCE_CLOSURE[:7])
    print("Source CI gate: Model 2 Bayesian VAR Guard #"+str(SOURCE_CI_NUMBER)+" / run "+str(SOURCE_CI_RUN)+" PASS")
    print("Manifest files verified: "+str(len(load_manifest())))
    print("Selected candidate: p=2 lambda=0.1 id="+SELECTED_ID)
    print("Prospective retuning/switching: prohibited")
    print("Tracked runtime artifacts: none")
    if gt("tag","--list",TAG):
        print("Release tag: "+TAG+" -> current release commit")
    else:
        print("Release tag: pending creation after release-metadata branch CI")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
