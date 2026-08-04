# Model 1D top-two miss and robustness audit

## Research question

Why did the frozen source fail the v0.3.6 top-two gate, and is its small soft-Brier advantage over rolling frequency robust?

## Frozen inputs

- source probabilities: committed v0.3.6 evidence;
- target: five-family `fixed_horizon_90d`;
- comparator: causal `rolling_frequency`;
- retrospective period: consumed and report-only;
- prospective shadow: beginning April 2026.

## Diagnostics

Every source miss is classified by realised-family rank, rank-two/rank-three gap, transition context, confidence context, adjacency inferred from modal dimension-sign signatures, and dimension attribution.

Source and rolling frequency are aligned by fold and month. Positive paired improvement means the source has the lower loss.

## Governance

Architecture success requires faithful use of v0.3.6 evidence, complete miss classification, unique fold-month rows, metric reconciliation, no-look-ahead inheritance, and prospective-shadow isolation. Architecture success is not a promotion decision.

## Dimension-evidence boundary

The frozen benchmark-prediction evidence has no month-level `growth_score`,
`inflation_score`, or `labour_score` fields. The separately located
`vintage_agreement.csv` contains only three aggregate mode comparisons and no
date column. It cannot provide causal fold-month attribution.

The audit therefore records dimension and adjacency attribution as unavailable.
This is an explicit evidence limitation, not a completed dimension diagnosis.

## Reconciliation boundary

The audit uses the exact v0.3.6 soft-log-loss floor:

```python
np.maximum(predicted, 1e-12)
```

Brier score, soft log loss, and top-two coverage must reconcile for both the
source and rolling frequency.
