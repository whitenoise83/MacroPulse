# MacroPulse Model 1D v0.3.2.post2

## Scope

Packaging dependency hotfix for Model 1D temporal diagnostics.

## Problem

`temporal_diagnostics_service.py` uses
`pandas.DataFrame.to_markdown()`. Pandas delegates Markdown table generation
to the optional `tabulate` package.

MacroPulse did not declare `tabulate` in `pyproject.toml`, so a clean editable
installation could pass all tests but fail while writing the diagnostics
report.

## Fix

The project dependencies now include:

`tabulate>=0.9.0`

After extracting this hotfix, run:

`pip install -e .`

No database initialisation is required.
