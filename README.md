# MacroPulse

## Model suite status

- **Model 1A — US GDP Nowcast:** production v1.0.0, frozen and validated.
- **Model 1B — US Inflation Nowcast:** production v1.0.0, frozen and validated.
- **Model 1C — US Labour Nowcast:** production v1.0.0, frozen and validated.
- **Model 1D — Unified US Macro State:** development v0.3.8 prospective shadow;
  research monitoring only, with no promotion authority.

## Production models

Models 1A, 1B, and 1C are separate governed production models. Their approved
policies, versions, hashes, validation histories, and approval records are
independent.

Model 1B provides governed monthly forecasts for headline/core CPI and
headline/core PCE. Forecasts are monthly log changes annualised by multiplying
by 1,200.

Model 1C provides governed monthly forecasts for nonfarm payroll change, the
unemployment rate, and average-hourly-earnings growth. Its stable 15-decision
target-stage policy and strictly prior `exp_weighted_q80` intervals are frozen
for production. Adaptive selection remains shadow-only.

## Production workflow

Use CMD inside Visual Studio Code:

```cmd
cd /d C:\Users\Cenk\OneDrive\MacroPulse
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
python scripts\initialise_database.py
```

Refresh and run the relevant governed source models before running downstream
macro-state operations.

Open the application:

```cmd
streamlit run app.py
```

## Model 1D v0.3.8 prospective shadow

Model 1D v0.3.8 compares the frozen v0.3.6 source candidate with the causal
`rolling_frequency` benchmark using immutable monthly predictions and
fixed-horizon 90-day outcomes.

It is a development research release. It cannot promote a candidate, switch
between models, blend probabilities, replace the source, or enter production.

Monthly operation:

```cmd
python scripts\run_macro_state_shadow_operations.py
```

Read-only status:

```cmd
python scripts\report_macro_state_shadow_status.py --no-write
```

Formal comparison is locked until at least 12 complete prospective target
months exist and all integrity checks pass. Before then, the only permitted
overall conclusion is `insufficient_prospective_evidence`.

See:

- `README_MODEL1D_v0.3.8.md`
- `MODEL1D_v0.3.8_PLAN.md`
- `docs/MODEL1D_v0.3.8_OPERATIONS.md`
- `MODEL1D_v0.3.8_RELEASE.json`

## Governance

Material changes to a production model require challenger evidence, a new
version, revalidation, and explicit model-owner approval.

Model 1D v0.3.8 must remain isolated from production promotion while the
prospective experiment is running. Local DuckDB files, backups, and generated
monitoring reports must not be committed.
