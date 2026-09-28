\
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/model3i_release_audits/MODEL3H_EVIDENCE_MANIFEST.json"
DIRS=[
    ROOT/"reports/model3h_final_evaluation",
    ROOT/"reports/model3h_pseudo_real_time",
]
records=[]
summaries=[]
for directory in DIRS:
    if not directory.exists():
        raise SystemExit(f"Missing Model 3H evidence directory: {directory.relative_to(ROOT)}")
    items=[]
    total=0
    for p in sorted(x for x in directory.rglob("*") if x.is_file()):
        data=p.read_bytes()
        rec={
            "path":p.relative_to(ROOT).as_posix(),
            "bytes":len(data),
            "sha256":hashlib.sha256(data).hexdigest(),
        }
        records.append(rec); items.append(rec); total+=len(data)
    if not items:
        raise SystemExit(f"Evidence directory contains no files: {directory.relative_to(ROOT)}")
    payload="\n".join(f"{x['sha256']}  {x['bytes']}  {x['path']}" for x in items).encode()
    summaries.append({
        "directory":directory.relative_to(ROOT).as_posix(),
        "file_count":len(items),
        "total_bytes":total,
        "directory_digest_sha256":hashlib.sha256(payload).hexdigest(),
    })
manifest={
    "manifest":"Model 3H empirical evidence inputs retained for Model 3I release reproducibility",
    "status":"PASS",
    "hash_algorithm":"sha256",
    "directories":summaries,
    "files":records,
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
print("Model 3H evidence manifest: PASS")
for x in summaries:
    print(f"{x['directory']}: files={x['file_count']} bytes={x['total_bytes']} digest={x['directory_digest_sha256']}")
