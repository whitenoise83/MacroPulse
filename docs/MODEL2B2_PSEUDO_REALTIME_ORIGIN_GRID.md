# Model 2B.2 — Pseudo-real-time Origin Grid

Model 2B.2 begins from closed Model 2B.1 commit `ff1217b3c154b2ae3dd0a6c931ce7200888c70b8` and freezes only the
historical origin-grid construction rule. It does not estimate a BVAR, select a
lag/shrinkage candidate, or choose an estimation/evaluation start.

## Origin rule

For each newly completed joint quarter `q`, the historical origin candidate is
the earliest successful common cached `as_of_date` at which the Model 2B.1
transformed panel reaches `q`.

Repeated cutoffs exposing the same last-complete quarter do not create extra
origins. A transition may advance by exactly one quarter; a decrease or skipped
quarter fails closed.

The first observed cache state is retained but marked `left_censored=true`,
because the cache may begin after that quarter actually first became available.
That row is not admissible for pseudo-real-time use.

For origin `q`, target labels are `q+1`, `q+2`, `q+4`, and `q+8`.

## Model 1 boundary

The baseline historical BVAR uses completed-quarter historical vintages only.
Model 1A/1B/1C outputs are not fabricated or backfilled. The governed Model 1
current-state anchor remains a separate prospective interface and does not enter
baseline parameter estimation in this workstream. Model 1D prospective outcomes
remain excluded.

## UNRATE canonical correction

`MODEL2_BOUNDARY.json` originally recorded UNRATE as a quarterly average.
Model 2B.1 established the governed rule as quarter-end UNRATE level for every
quarter. 2B.2 aligns the top-level boundary to that already-closed rule and
records the amendment provenance; this is not a new modelling choice.

At 2B.1 closure the cache contained 213 successful common cutoffs from
2015-01-15 through 2026-06-30, with 47 observed last-complete-quarter states
from 2014Q3 through 2026Q1. The first state is left-censored, leaving 46
observable non-left-censored origin candidates. These counts are closure
evidence, not permanent limits.
