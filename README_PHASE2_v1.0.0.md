# MacroPulse Phase II Platform v1.0.0

## Release status

MacroPulse Phase II is closed as platform release **v1.0.0**.

The release closure is based on successful external CI evidence from:

- workflow: `Phase II Platform Guard`
- successful run: `#2`
- GitHub run ID: `31307316856`
- validated commit: `bd98dde68b32b9b71e54c8cc797205fa5627641b`
- duration: `3m 12s`

The final release tag is:

```text
phase2-platform-v1.0.0
```

The tag is created only after the closure commit itself passes the Phase II
Platform Guard.

## Scope

Phase II is a governed platform-integration layer over the existing model
suite. It does not introduce a new macro model.

Completed workstreams:

- 2A — bootstrap and platform contract;
- 2B — read-only health and freshness;
- 2C — unified governed orchestration;
- 2D — deterministic macro snapshot;
- 2E — integrated read-only dashboard;
- 2F — operational hardening and release closure.

## Model boundary

- Model 1A: production v1.0.0;
- Model 1B: production v1.0.0;
- Model 1C: production v1.0.0;
- Model 1D: development v0.3.8 prospective shadow.

Model 1D remains research-only and has no production promotion authority.

The Phase II release does not alter:

- Model 1A–1C production specifications;
- the frozen Model 1D candidate;
- the Model 1D comparator;
- the Model 1D target definition or horizon;
- Model 1D probability logic;
- append-only prospective evidence;
- published Model 1D release tags.

## Operational entry points

Read-only status:

```cmd
python scripts\report_platform_status.py
```

Governed orchestration dry run:

```cmd
python scripts\run_platform_operations.py
```

Explicit current-day execution:

```cmd
python scripts\run_platform_operations.py --execute
```

Deterministic snapshot:

```cmd
python scripts\export_macro_snapshot.py --as-of YYYY-MM-DD
```

Dashboard:

```cmd
streamlit run app.py
```

Release verification:

```cmd
python scripts\verify_phase2_release.py
```

After the final release tag exists:

```cmd
python scripts\verify_phase2_release.py --require-tag
```

## Release discipline

The Phase II v1.0.0 release baseline should be treated as closed after the
release tag is published. Subsequent feature development should use a new
development branch/version rather than silently changing the released
baseline.
