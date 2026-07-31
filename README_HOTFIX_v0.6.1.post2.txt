MacroPulse v0.6.1.post2 - Coherent upper-tail validation hotfix

This patch changes validation logic only. Forecasts, model policy, staged backtest
results, database schema, and data are unchanged.

Reason
------
The previous p90 gate compared production with whichever static model had the
lowest p90, even when that model was materially worse on RMSE, MAE, and maximum
error. At the pre-advance-release stage this selected Bridge Ridge as the p90
benchmark despite its substantially worse overall and crisis-period errors.

Fix
---
The p90 comparator is now chosen only from static models that are also within the
existing RMSE, MAE, and maximum-error competitiveness limits. This creates one
coherent accuracy-eligible comparator set instead of a separate best model for
each loss statistic. The p90 threshold remains unchanged at 1.20.

No staged backtest rerun is required. Run scripts\run_validation.py and then, if
there are no failed gates, scripts\generate_freeze_assessment.py.
