\
from __future__ import annotations
from datetime import date
import json
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

from macropulse.slack.production import (
    MODEL3_SELECTED_CANDIDATE,
    PRODUCTION_CURRENT_CLASS,
    deterministic_export_hash,
    deterministic_export_payload,
    production_current_estimate,
)

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"data/macropulse.duckdb"
OUT=ROOT/"reports/model3i_release_audits/MODEL3I_PRODUCTION_SMOKE_TEST.json"
AS_OF=date(2026,6,30)
PLANNED_TAG="model3-potential-output-v1.0.0"

if not DB.exists():
    raise SystemExit("Missing local DuckDB for production smoke test: "+str(DB))
con=duckdb.connect(str(DB),read_only=True)
snapshot=con.execute("""
SELECT series_id, observation_date, value
FROM historical_snapshots
WHERE series_id IN ('GDPC1','PCEPILFE','UNRATE')
  AND as_of_date=?
ORDER BY series_id, observation_date
""",[AS_OF]).fetchdf()
con.close()
if snapshot.empty:
    raise SystemExit("Latest complete Model 3 exact-vintage snapshot is empty.")
future=int((pd.to_datetime(snapshot["observation_date"]).dt.date>AS_OF).sum())
if future:
    raise SystemExit(f"Production smoke snapshot contains {future} future-dated rows.")

a=production_current_estimate(snapshot,as_of_date=AS_OF,release_identity=PLANNED_TAG)
b=production_current_estimate(snapshot,as_of_date=AS_OF,release_identity=PLANNED_TAG)
ha=deterministic_export_hash(a); hb=deterministic_export_hash(b)
if ha != hb:
    raise SystemExit("Deterministic production export hash differs across repeated fits.")
if a.provenance.selected_candidate != MODEL3_SELECTED_CANDIDATE:
    raise SystemExit("Production selected candidate is not governed 3D.")
if a.provenance.estimate_class != PRODUCTION_CURRENT_CLASS:
    raise SystemExit("Production estimate class is not production_current_endpoint.")
vals=np.asarray([
    a.observed_log_output,a.potential_log_output,a.potential_output_level,
    a.potential_output_growth_annualized_pct,a.output_gap_pct
],dtype=float)
if not np.isfinite(vals).all():
    raise SystemExit("Production smoke output contains non-finite values.")
record={
    "audit":"Model 3I real-data production smoke test",
    "status":"PASS",
    "release_status":"pre_tag_validation",
    "planned_release_tag":PLANNED_TAG,
    "as_of_date":AS_OF.isoformat(),
    "snapshot_rows":int(len(snapshot)),
    "future_dated_rows":future,
    "deterministic_repeated_fit":True,
    "export_sha256":ha,
    "current_estimate":deterministic_export_payload(a),
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
print("Model 3I production smoke test: PASS")
print("as_of_date:",AS_OF)
print("sample:",a.provenance.sample_first_quarter,"to",a.provenance.sample_last_quarter,"n=",a.provenance.n_observations)
print("current quarter:",a.quarter)
print("output gap pct:",a.output_gap_pct)
print("potential growth annualized pct:",a.potential_output_growth_annualized_pct)
print("export sha256:",ha)
