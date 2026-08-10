# Phase 3D — Revision & Release-Impact Analytics Contract

## Status

Phase 3D implementation contract.

Phase 3D analyses changes between successive governed production forecasts and
associates those changes with scheduled source releases occurring between the
governed information cutoffs.

The association is descriptive. Phase 3D does not claim causality.

## 1. Scope

Phase 3D is read-only and in-memory.

It consumes:

- governed 1A/1B/1C forecast history via the Phase 3B forecast collector;
- governed run information-set tables;
- the existing MacroPulse release calendar.

It does not:

- execute Models 1A–1D;
- mutate governed forecasts;
- mutate source observations;
- create or migrate database tables;
- download releases;
- modify model parameters;
- automatically promote/demote/switch a model;
- include Model 1D as a production revision series.

## 2. Comparable forecast identity

Forecast revisions are computed only within:

```text
component + target_series + target_period
```

A change from one target period to another is not a revision.

Examples:

```text
July CPI run A -> July CPI run B       comparable revision
2026Q2 GDP -> 2026Q3 GDP              not comparable
July payroll forecast -> August       not comparable
```

The first governed forecast for each comparable identity is labelled:

```text
baseline_no_previous
```

Later observations are:

```text
comparable_revision
```

## 3. Sequential revision

For comparable runs:

```text
revision =
    current_forecast_value - previous_forecast_value

absolute_revision =
    abs(revision)
```

Direction:

```text
revision > 0    upward
revision < 0    downward
revision == 0   unchanged
```

Phase 3D also reports revisions in the 80% interval bounds and interval width.

## 4. Cumulative revision

Within each comparable target identity:

```text
cumulative_revision =
    current_forecast_value - first_forecast_value
```

The first forecast therefore has cumulative revision zero.

No cumulative revision crosses target-period boundaries.

## 5. Stage transition

Phase 3D records:

```text
previous_forecast_stage
current_forecast_stage
stage_changed
```

A stage change is metadata attached to a revision, not an explanation for it.

## 6. Scheduled release association

Each production component already has a governed information-set table:

```text
1A -> nowcast_information_sets
1B -> inflation_live_information_sets
1C -> labour_live_information_sets
```

For a comparable revision, Phase 3D identifies source series in the current
governed information set and queries the existing release calendar for:

```text
previous_information_cutoff < release_date
release_date <= current_information_cutoff
```

This window is intentional:

```text
(previous cutoff, current cutoff]
```

A same-date cutoff pair has no calendar window.

## 7. Information-set advance

A scheduled release is not automatically treated as newly incorporated data.

For each associated source series, Phase 3D compares:

```text
MAX(observation_date) in previous governed information set
MAX(observation_date) in current governed information set
```

and records:

```text
information_set_advanced
```

This provides stronger descriptive evidence than calendar timing alone.

It still does not establish causal forecast impact.

## 8. Association states

Comparable revisions may receive:

```text
no_scheduled_release
scheduled_releases_none_advanced
scheduled_releases_with_source_advance
same_cutoff_no_calendar_window
missing_information_set_contract
missing_cutoff
invalid_cutoff_order
```

Baseline rows receive:

```text
baseline_no_previous
```

## 9. Causality boundary

Phase 3D reports temporal association only.

It must not describe a forecast change as:

- caused by;
- driven by;
- attributable to;
- explained by;

a release unless a separately governed causal identification design is added
in a future workstream.

The machine-readable report therefore declares:

```text
release_association_is_causal = false
```

and every release-event row declares:

```text
causality_claim = false
```

## 10. Determinism

For the same:

- governed forecast history;
- governed information sets;
- release calendar;
- evaluation `as_of`;

the semantic revision/release report is deterministic.

No wall-clock timestamp is included.

## 11. CLI

Current report:

```cmd
python scripts\report_forecast_revisions.py
```

Historical report:

```cmd
python scripts\report_forecast_revisions.py --as-of YYYY-MM-DD
```

Include event detail:

```cmd
python scripts\report_forecast_revisions.py --events
```

JSON:

```cmd
python scripts\report_forecast_revisions.py --json
```

Filters:

```cmd
python scripts\report_forecast_revisions.py --component 1B
python scripts\report_forecast_revisions.py --target-series CPIAUCSL
```

The CLI writes no file.

## 12. Model 1D boundary

Model 1D remains prospective research-only.

Phase 3D does not:

- compare Model 1D research candidates;
- associate its outcomes with production releases;
- tune or switch its source/benchmark;
- create promotion authority.
