# MacroPulse Model 1D v0.2.0.post3

## Defect

The historical reconstruction generated only calendar month-end dates.

For a command ending on `2026-08-01`, the last evaluated date was therefore
`2026-07-31`. The complete inflation and labour production runs had information
cutoff `2026-08-01`, so the valid terminal source bundle was never evaluated.

## Fix

The reconstruction date set now contains:

1. all calendar month ends within the requested interval; and
2. the explicitly requested end date when it is not already a month end.

Thus:

`--start 2015-01-01 --end 2026-08-01`

evaluates both `2026-07-31` and the terminal as-of date `2026-08-01`.

The no-look-ahead rule remains unchanged: every selected source cutoff must be
on or before its state date.

## Expected current coverage

Because historical Model 1B and Model 1C live-run vintages were not stored back
to 2015, the first reconstruction may contain only the current terminal state.
That is an evidence-coverage limitation, not fabricated history.
