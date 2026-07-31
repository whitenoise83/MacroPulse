# Model 1B v0.2.0.post1 - FRED resilience hotfix

This hotfix adds bounded exponential retries for transient FRED/ALFRED failures
(HTTP 429, 500, 502, 503 and 504, plus connection timeouts). A single release
snapshot that remains unavailable after all retries is recorded as an issue and
the long vintage backtest continues rather than aborting.

Previously cached snapshots remain valid and are automatically reused on rerun.
