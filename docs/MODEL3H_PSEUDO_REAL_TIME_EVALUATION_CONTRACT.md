# Model 3H — Pseudo-Real-Time Evaluation & Selection

## Purpose

Model 3H evaluates Model 3 structural slack candidates using genuine recursive
pseudo-real-time endpoints. It is the first workstream allowed to establish
`filtered_real_time_endpoint` estimates.

At every historical origin `t`, the candidate is fitted using only the exact
vintage information set available at `t`. Parameters are re-estimated at that
origin. Full-sample filtered or smoothed paths must never be relabelled as
real-time estimates.

## Frozen predecessor

Model 3G commit:

`86e58f9c7a1bcec8818c6233bc658675293ffed3`

## Candidate set

- 3D: GDP-only state-space potential output.
- 3E-A: GDP plus inflation.
- 3E-B: GDP plus inflation and unemployment.

Model 3C benchmarks are diagnostic references, not structural candidates.

## Predeclared hierarchy

Selection rules are frozen before empirical 3H results are inspected.

1. Real-time estimability and origin coverage.
2. Numerical and econometric admissibility.
3. Revision and endpoint stability.
4. Economic diagnostic evidence.

No arbitrary weighted composite score is used. Expected Phillips and Okun signs
are recorded as evidence rather than imposed as coefficient restrictions.

Model 4 performance is prohibited as a Model 3 selection criterion. Model 1D's
prospective-validation status is not a Model 3H selection gate.

## Bootstrap boundary

The bootstrap establishes contracts, origin/result structures, validation and
diagnostic primitives only. It does not declare a production winner. Empirical
selection requires a subsequent governed 3H evaluation run under these frozen
rules.

No database writes, production promotion, or mutation of Models 1, 2, or frozen
Model 3 predecessor workstreams is permitted.

## Recursive evaluation engine

For every Model 3B inventory row marked admissible for pseudo-real-time use, 3H reloads that row's exact-vintage snapshot, rebuilds the quarterly panel, verifies the terminal quarter, and independently refits 3D, 3E-A and 3E-B.

The endpoint is the terminal observation of the candidate's filtered path from that origin-truncated fit. 3H relabels only that terminal value as `filtered_real_time_endpoint`. Smoothed estimates are not used to construct the real-time endpoint.

Candidate estimation failures are retained as failed origin/candidate records rather than silently deleting difficult origins.
