# Changelog — Model 1D v0.2.0.post3

## Fixed

- Added the explicit CLI end date as a terminal as-of reconstruction date.
- Prevented duplicate dates when the end date is already a month end.
- Aligned `months_requested` metadata with the actual reconstruction-date set.
- Improved the empty-history error message.
- Added terminal-date regression tests.
