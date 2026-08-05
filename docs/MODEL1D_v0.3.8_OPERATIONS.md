# Model 1D v0.3.8 Prospective Shadow Operations

## Purpose

This layer operates and monitors the frozen Model 1D v0.3.8 prospective
transition shadow. It does not change the prediction engine, source candidate,
comparator, target definition, probability contract, or outcome resolver.

## Monthly command

Run once after the governed Model 1A, 1B, and 1C source forecasts are available:

```cmd
python scripts\run_macro_state_shadow_operations.py
```

The command is idempotent for the current state month:

1. it creates the monthly shadow prediction only when that month is absent;
2. it attempts to resolve every eligible older shadow run;
3. it writes a monitoring report;
4. it never overwrites a prediction or outcome.

For a controlled historical cutoff:

```cmd
python scripts\run_macro_state_shadow_operations.py --as-of 2026-08-05
```

Future cutoffs are prohibited.

## Read-only status command

```cmd
python scripts\report_macro_state_shadow_status.py
```

Use `--no-write` to inspect the database without producing report files.

## Dashboard

Start MacroPulse normally:

```cmd
streamlit run app.py
```

Open **Model 1D Shadow**. The page is read-only.

## Evidence lock

A formal source-versus-rolling-frequency comparison remains locked until all of
the following are true:

- at least 12 complete prospective target months exist;
- every run has exactly two prediction rows;
- every run has exactly three dimension rows;
- every resolved month has exactly two outcome rows;
- all probability sums and no-look-ahead checks pass;
- no outcome was resolved before its fixed-horizon target became available.

Even after the lock opens, the comparison remains research-only. Model 1D v0.3.8
has no promotion, switching, blending, or source-replacement authority.

## Runtime reports

Reports are written under:

```text
reports/macro_state_shadow_monitoring/
```

Each report package contains run status, integrity checks, benchmark metrics,
paired monthly scores, transition diagnostics, readiness, metadata, and a
Markdown summary.
