# Model 1C Owner Signoff Checklist

The model owner should verify that the freeze report shows:

- Candidate validation: pass, 39 passed, 0 failed, 0 warnings.
- Operational validation: pass, 20 passed, 0 failed, 0 warnings.
- Exactly three governed labour headlines.
- Stable policy controls every headline.
- Adaptive forecasts remain shadow-only.
- Live intervals use `exp_weighted_q80` with prior-only history.
- Comparable news decomposition exists for all three targets.
- Maximum news-reconciliation residual is within tolerance.
- Configuration, code, information-set, model-state, and governance hashes exist.
- Candidate and operational reports are preserved.
- The Model 1C model card is present.

A passing freeze assessment establishes readiness for explicit owner approval. It
does not itself promote Model 1C to production.
