import numpy as np
from macropulse.data.repository import MacroRepository
from macropulse.slack.data import REQUIRED_SERIES,build_quarterly_panel
from macropulse.slack.state_space import fit_state_space
r=MacroRepository(); marks=", ".join(["?"]*len(REQUIRED_SERIES))
q="SELECT MAX(as_of_date) FROM (SELECT as_of_date FROM snapshot_downloads WHERE status='success' AND series_id IN ("+marks+") GROUP BY as_of_date HAVING COUNT(DISTINCT series_id)=?)"
with r.connect(read_only=True) as c:d=c.execute(q,[*REQUIRED_SERIES,len(REQUIRED_SERIES)]).fetchone()[0]
s=r.historical_snapshot(as_of_date=d,series_ids=list(REQUIRED_SERIES));p=build_quarterly_panel(s,d)
f=fit_state_space(p.real_gdp_log,maxiter=2000);x=f.estimates[f.estimates.estimate_class=="smoothed_revised"];z=f.diagnostics
roots=np.roots([-z.phi2,-z.phi1,1.])
print("snapshot",d,"sample",p.index[0],"to",p.index[-1],"n",len(p))
print("converged",z.converged,"sigma_growth",z.sigma_trend_growth,"sigma_gap",z.sigma_gap)
print("phi1",z.phi1,"phi2",z.phi2,"min_root_modulus",float(np.min(np.abs(roots))))
print("gap_range",float(x.output_gap_pct.min()),float(x.output_gap_pct.max()),"latest_gap",float(x.output_gap_pct.iloc[-1]))
print("growth_range",float(x.potential_output_growth_annualized_pct.min()),float(x.potential_output_growth_annualized_pct.max()))
print("potential_finite",bool(np.isfinite(x.potential_output_level).all()))
assert x.output_gap_pct.abs().max()<50 and np.isfinite(x.potential_output_level).all()
print("REAL-DATA 3D CORRECTIVE ADMISSIBILITY: PASS")
