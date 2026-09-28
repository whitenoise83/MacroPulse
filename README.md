# MacroPulse

MacroPulse is a proprietary, commercially developed macroeconomic intelligence platform for vintage-aware nowcasting, forecasting, macro-state measurement, and potential-output/slack estimation.

> **Commercial / proprietary software.** The source code in this repository is publicly visible for development and review purposes, but it is **not open source**. No right to use, copy, modify, distribute, sublicense, commercialize, or create derivative works is granted except under a separate written agreement with the copyright holder. See `LICENSE` and `COMMERCIAL_LICENSING.md`.

## Current governed model suite

| Model | Purpose | Governed status |
| --- | --- | --- |
| **1A — US GDP Nowcast** | Real-time US GDP nowcasting | Production v1.0.0 |
| **1B — US Inflation Nowcast** | Headline/core CPI and PCE nowcasting | Production v1.0.0 |
| **1C — US Labour Nowcast** | Payrolls, unemployment and earnings nowcasting | Production v1.0.0 |
| **1D — Unified US Macro State** | Unified macro-state classification | v0.3.8 prospective shadow / research monitoring |
| **2 — Bayesian VAR** | Multivariate macro forecasting, predictive distributions, IRF/FEVD and governed scenarios | **v1.0.2 released** |
| **3 — Potential Output & Macroeconomic Slack** | Potential GDP, trend growth, output gap and forward-gap integration | **v1.0.0 released** |

### Frozen release tags

- `model2-bvar-v1.0.2`
- `model3-pseudo-real-time-v1.0.0`
- `model3-potential-output-v1.0.0`

Existing governed release tags are immutable and must never be moved or recreated.

## Streamlit application

The current application exposes the governed Model 1 views plus read-only Model 2 and Model 3 pages:

- Bayesian VAR Forecasts & Scenarios
- Potential Output & Slack
- GDP / Inflation / Labour nowcasts
- Unified Macro State / Model 1D Shadow
- backtesting, comparison, history, validation and governance views

Run locally:

```cmd
cd /d C:\Users\Cenk\OneDrive\MacroPulse
.venv\Scripts\activate
pip install -e .
streamlit run app.py
```

A FRED API key is required for data-download operations. Copy `.env.example` to `.env` and provide your own key.

## Model 2 — Bayesian VAR v1.0.2

The governed Model 2 release uses the selected BVAR(2) specification with shrinkage 0.1. It provides:

- horizons 1, 2, 4 and 8 quarters;
- predictive distributions;
- recursive-Cholesky IRF/FEVD;
- mechanically conditioned scenario paths;
- no automatic candidate reselection or model switching;
- no database-write authority from the production forecast interface.

See `MODEL2_RELEASE.json` and `README_MODEL2_v1.0.2.md`.

## Model 3 — Potential Output & Macroeconomic Slack v1.0.0

The governed Model 3 release freezes **3D — State-Space Potential Output**, selected using pseudo-real-time evidence.

Production semantics:

- current estimate: `production_current_endpoint`;
- revised historical estimate: `smoothed_revised`;
- full-sample filtered history is **not** claimed to be historical real-time evidence;
- forward potential continuation is deterministic;
- no forward potential-output uncertainty claim is made;
- no Model 1 or Model 2 mutation;
- no Model 4-based retuning;
- no automatic candidate switching.

See `MODEL3_RELEASE.json`, `README_MODEL3_v1.0.0.md`, and `VALIDATION_MODEL3_v1.0.0.txt`.

## Installation

Python 3.11+ is required.

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .
```

Development/test dependencies:

```cmd
pip install -r requirements-dev.txt
```

The runtime dependency set is declared in `pyproject.toml`. `requirements.txt` remains a compatible deployment-oriented dependency list.

## Data and external services

MacroPulse can use FRED/ALFRED and other external data sources. Rights in third-party data and services remain with their respective providers and are subject to their own terms.

Local databases, runtime snapshots, backups and generated operational reports must not be committed.

## Governance

Material changes to governed production models require explicit versioning, validation evidence, and release controls. Release-specific verifiers and CI workflows are retained as part of the audit trail.

Repository-wide development should proceed through a protected canonical branch with required CI. See `docs/GITHUB_REPOSITORY_HARDENING.md`.

## Security

Do not commit API keys, tokens, credentials, private datasets, or customer information. Security issues should be reported privately using GitHub's private vulnerability reporting / security-advisory mechanism where available. See `SECURITY.md`.

## License

Copyright © 2026 Cenk Ufuk Yildiran. All rights reserved.

MacroPulse is proprietary commercial software. See `LICENSE` and `COMMERCIAL_LICENSING.md`.
