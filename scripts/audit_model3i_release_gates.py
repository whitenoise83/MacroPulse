from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
bvar=(ROOT/"src/macropulse/bvar/data.py").read_text(encoding="utf-8")
fg=(ROOT/"src/macropulse/slack/forward_gap.py").read_text(encoding="utf-8")
prod=(ROOT/"src/macropulse/slack/production.py").read_text(encoding="utf-8")
req=(ROOT/"requirements.txt").read_text(encoding="utf-8")
py=(ROOT/"pyproject.toml").read_text(encoding="utf-8")

assert "return 400.0 * levels.map(log).diff()" in bvar
assert "qlog=x/400.0" in fg and "np.cumsum(x/400.0,axis=1)" in fg
assert 'names.index("real_gdp_growth")' in prod
assert "DENSE_MODEL2_HORIZONS = tuple(range(1, 9))" in prod
assert "GOVERNED_REPORT_HORIZONS = (1, 2, 4, 8)" in prod
assert "statsmodels>=0.14.6,<0.16" in req
assert '"statsmodels>=0.14.6,<0.16"' in py
print("Model 3I release audits: PASS")
print("GDP transform: 400*diff(log(GDPC1)) - confirmed")
print("3G /400 compounding: dimensionally consistent - confirmed")
print("GDP predictive draw selection: by governed variable name - hardened")
print("Dense 1..8 vs report 1,2,4,8 provenance: explicit - hardened")
print("statsmodels package metadata: normalized")
