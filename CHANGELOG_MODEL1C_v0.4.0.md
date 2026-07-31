# Model 1C v0.4.0 changelog

- Added a predeclared stable policy for all 15 target-stage combinations.
- Added a strictly prior-only adaptive shadow selector.
- Added robust switching hurdles and tail, maximum-error, median-error, and
  directional-accuracy guards.
- Added common-sample fixed-versus-shadow performance comparisons.
- Added shadow switching-stability diagnostics.
- Added fixed-policy regime performance reporting.
- Added stable and shadow diagnostics using the existing prior-only
  `exp_weighted_q80` calibration.
- Added CSV and Markdown policy-evaluation reports.
- Added policy unit tests.
- Model 1A and Model 1B production specifications remain unchanged.
