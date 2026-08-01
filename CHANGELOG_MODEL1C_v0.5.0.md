# Model 1C v0.5.0

- Added formal candidate validation for the stable 15-decision labour policy.
- Added coherent tail and maximum-error comparators restricted to models that are
  also competitive on RMSE and MAE.
- Added target-appropriate bias gates for payrolls, unemployment, and earnings.
- Added directional-accuracy and economic-regime gates.
- Added prior-only adaptive-shadow common-sample and switching checks.
- Added selected-policy `exp_weighted_q80` coverage, history, width, score, and
  no-look-ahead checks.
- Linked candidate validation to the prior passing vintage validation and successful
  interval calibration.
- No point forecasts, historical outcomes, calibration rows, or production models
  are modified.
