# Model 3I Selected-3D Fixed-Quarter Revision Audit

**Status: PASS — not a release blocker.**

All 46 recursive 3D refits succeeded. For 45 quarters that were once a
real-time terminal endpoint and later re-estimated at subsequent vintages:

- latest-vintage revision MAE: **0.371 pp**
- latest-vintage revision RMSE: **0.685 pp**
- latest-vintage maximum absolute revision: **3.798 pp**
- mean pathwise maximum absolute revision: **0.463 pp**
- maximum pathwise absolute revision: **4.702 pp**

The instability is concentrated in the extraordinary COVID shock window:

| Subperiod | n | MAE (pp) | RMSE (pp) | Max abs (pp) |
|---|---:|---:|---:|---:|
| 2020Q1–2021Q4 | 8 | 1.011 | 1.508 | 3.798 |
| Non-COVID | 37 | 0.232 | 0.281 | 0.623 |

The largest revision is 2020Q2: the real-time terminal gap estimate was about
-0.201%, while the later estimate is about -3.998%; its pathwise maximum
absolute revision is 4.702 pp.

This is a **3I robustness/release diagnostic**, not a new 3H selection
criterion. No post-hoc revision threshold is introduced, and the governed
selection of 3D is not reopened. Historical full-sample filtered paths are not
relabelled as real-time estimates.
