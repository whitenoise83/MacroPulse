# Model 1D v0.3.8 — Prospective Transition Shadow

## Status

- Model: `US_MACRO_STATE_1D`
- Version: `0.3.8`
- Lifecycle: `development`
- Evidence type: `prospective_shadow`
- Promotion authority: `none`
- Parent release: `v0.3.7`
- Frozen source specification: `v0.3.6`
- Frozen source candidate: `expanding_robust_z__policy__equal__sensitive__independent_normal`
- Primary comparator: `rolling_frequency`

## Objective

Collect genuine prospective evidence on whether the frozen source or the
rolling-frequency benchmark performs more reliably during stable and
transition periods.

This release does not select, tune, blend, promote, or replace a model.

## Evidence boundary

Predictions must be stored before target outcomes are available.

No latest-revised target may be substituted retrospectively.

Previously stored prediction rows must be append-only and immutable.

All target evaluation must use the fixed-horizon target contract established
in Model 1D v0.3.6.

## Required prediction evidence

For each state month and benchmark, persist:

- shadow run ID
- model ID
- model version
- state date
- information cutoff
- prediction timestamp
- target mode
- target horizon
- expected target availability date
- benchmark ID
- predicted family
- five-family probability vector
- top-one, top-two, and top-three rankings
- top-one, top-two, and top-three probabilities
- top-one/top-two probability gap
- entropy
- probability sum
- probability-vector hash
- source lineage
- information-set hash
- source-bundle hash
- config hash
- code hash
- Git commit
- no-look-ahead status

## Required dimension evidence

Store dated monthly values for:

- growth score
- inflation score
- labour score

Each dimension row must include its source model ID, source model version,
source run ID, source information cutoff, source data-as-of date, and source
hash.

Dimension scores must use only information available at the prediction cutoff.

## Outcome resolution

When the fixed-horizon target becomes available, append:

- outcome ID
- shadow run ID
- model version
- state date
- benchmark ID
- resolution timestamp
- target mode
- target horizon
- target availability date
- target vintage ID
- realised target family
- realised target probability vector
- target confidence
- probability assigned to the realised family
- Brier score
- log loss
- top-one hit
- top-two hit
- top-three hit
- previous resolved actual family
- transition flag
- target hash
- evaluation hash
- no-look-ahead status

## Frozen persistence design

### `macro_state_shadow_runs`

```sql
CREATE TABLE IF NOT EXISTS macro_state_shadow_runs (
    shadow_run_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    state_date DATE NOT NULL,
    information_cutoff DATE NOT NULL,

    target_mode VARCHAR NOT NULL,
    target_horizon_days INTEGER NOT NULL,
    target_expected_available_date DATE NOT NULL,

    source_candidate_id VARCHAR NOT NULL,
    source_evidence_version VARCHAR NOT NULL,
    primary_comparator VARCHAR NOT NULL,

    source_macro_state_run_id VARCHAR NOT NULL,
    gdp_run_id VARCHAR NOT NULL,
    inflation_run_id VARCHAR NOT NULL,
    labour_run_id VARCHAR NOT NULL,

    config_hash VARCHAR NOT NULL,
    code_hash VARCHAR NOT NULL,
    git_commit VARCHAR,
    information_set_hash VARCHAR NOT NULL,
    source_bundle_hash VARCHAR NOT NULL,

    no_look_ahead_pass BOOLEAN NOT NULL,
    status VARCHAR NOT NULL,
    governance_json VARCHAR NOT NULL,
    notes VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_state_shadow_run_month
ON macro_state_shadow_runs(model_version, state_date);

CREATE INDEX IF NOT EXISTS idx_macro_state_shadow_run_resolution
ON macro_state_shadow_runs(
    target_expected_available_date,
    state_date,
    status
);
```

### `macro_state_shadow_predictions`

```sql
CREATE TABLE IF NOT EXISTS macro_state_shadow_predictions (
    shadow_run_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    state_date DATE NOT NULL,
    information_cutoff DATE NOT NULL,
    prediction_timestamp TIMESTAMP NOT NULL,

    benchmark_id VARCHAR NOT NULL,
    predicted_family VARCHAR NOT NULL,
    predicted_probabilities_json VARCHAR NOT NULL,

    top1_family VARCHAR NOT NULL,
    top2_family VARCHAR NOT NULL,
    top3_family VARCHAR NOT NULL,
    top1_probability DOUBLE NOT NULL,
    top2_probability DOUBLE NOT NULL,
    top3_probability DOUBLE NOT NULL,

    top1_top2_gap DOUBLE NOT NULL,
    entropy DOUBLE NOT NULL,
    probability_sum DOUBLE NOT NULL,
    probability_vector_hash VARCHAR NOT NULL,

    no_look_ahead_pass BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_state_shadow_prediction_unique
ON macro_state_shadow_predictions(shadow_run_id, benchmark_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_state_shadow_prediction_month
ON macro_state_shadow_predictions(
    model_version,
    state_date,
    benchmark_id
);
```

### `macro_state_shadow_dimensions`

```sql
CREATE TABLE IF NOT EXISTS macro_state_shadow_dimensions (
    shadow_run_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    state_date DATE NOT NULL,
    information_cutoff DATE NOT NULL,

    dimension VARCHAR NOT NULL,
    score DOUBLE NOT NULL,
    lower_score DOUBLE NOT NULL,
    upper_score DOUBLE NOT NULL,
    label VARCHAR NOT NULL,
    confidence DOUBLE NOT NULL,

    source_model_id VARCHAR NOT NULL,
    source_model_version VARCHAR NOT NULL,
    source_run_id VARCHAR NOT NULL,
    source_information_cutoff DATE NOT NULL,
    source_data_as_of DATE,
    source_hash VARCHAR NOT NULL,

    no_look_ahead_pass BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_state_shadow_dimension_unique
ON macro_state_shadow_dimensions(shadow_run_id, dimension);

CREATE INDEX IF NOT EXISTS idx_macro_state_shadow_dimension_month
ON macro_state_shadow_dimensions(
    model_version,
    state_date,
    dimension
);
```

### `macro_state_shadow_outcomes`

```sql
CREATE TABLE IF NOT EXISTS macro_state_shadow_outcomes (
    outcome_id VARCHAR PRIMARY KEY,
    shadow_run_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    state_date DATE NOT NULL,
    benchmark_id VARCHAR NOT NULL,

    resolved_at TIMESTAMP NOT NULL,
    target_mode VARCHAR NOT NULL,
    target_horizon_days INTEGER NOT NULL,
    target_available_date DATE NOT NULL,
    target_vintage_id VARCHAR NOT NULL,

    actual_family VARCHAR NOT NULL,
    actual_probabilities_json VARCHAR NOT NULL,
    actual_confidence DOUBLE NOT NULL,

    actual_probability DOUBLE NOT NULL,
    brier_score DOUBLE NOT NULL,
    log_loss DOUBLE NOT NULL,
    top1_hit BOOLEAN NOT NULL,
    top2_hit BOOLEAN NOT NULL,
    top3_hit BOOLEAN NOT NULL,

    previous_actual_family VARCHAR,
    transition_flag BOOLEAN NOT NULL,

    target_hash VARCHAR NOT NULL,
    evaluation_hash VARCHAR NOT NULL,
    no_look_ahead_pass BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_state_shadow_outcome_unique
ON macro_state_shadow_outcomes(shadow_run_id, benchmark_id);

CREATE INDEX IF NOT EXISTS idx_macro_state_shadow_outcome_month
ON macro_state_shadow_outcomes(
    model_version,
    state_date,
    benchmark_id
);
```

## Frozen governance configuration

```yaml
prospective_transition_shadow:
  model_version: "0.3.8"
  lifecycle_status: "development"
  evidence_type: "prospective_shadow"
  promotion_authority: "none"
  parent_release: "0.3.7"

  frozen_source:
    model_version: "0.3.6"
    candidate_id: "expanding_robust_z__policy__equal__sensitive__independent_normal"
    specification_changes_prohibited: true

  comparator:
    benchmark_id: "rolling_frequency"
    primary: true
    adaptive_switching_prohibited: true
    blending_prohibited: true

  target:
    mode: "fixed_horizon_90d"
    horizon_days: 90
    latest_revised_substitution_prohibited: true
    target_must_be_available_before_resolution: true

  probability_contract:
    family_order:
      - adverse_supply
      - benign_expansion
      - contraction
      - inflationary_expansion
      - mixed
    required_sum: 1.0
    sum_tolerance: 1.0e-10
    log_loss_floor: 1.0e-12

  persistence:
    append_only: true
    updates_prohibited: true
    deletes_prohibited: true
    prediction_overwrite_prohibited: true
    duplicate_month_benchmark_prohibited: true
    outcome_before_target_availability_prohibited: true

  required_dimensions:
    - growth
    - inflation
    - labour

  minimum_evidence:
    complete_target_months: 12

  allowed_conclusions:
    - source_advantage_appears_prospectively_robust
    - source_advantage_remains_statistically_inconclusive
    - rolling_frequency_not_materially_inferior
    - insufficient_prospective_evidence

  prohibited_conclusions:
    - candidate_approved
    - production_approved
    - adaptive_switching_approved
    - source_replaced
    - comparator_replaced
```

## Persistence invariants

The four shadow tables are append-only.

The repository and service layers must not use:

- `UPDATE`
- `DELETE`
- `INSERT OR REPLACE`
- `UPSERT`
- silent duplicate suppression

Duplicate attempts must fail through both unique indexes and service-level
preflight checks.

A valid monthly prediction write must contain:

- exactly one run row
- exactly two prediction rows: `source` and `rolling_frequency`
- exactly three dimension rows: `growth`, `inflation`, and `labour`
- no outcome rows at prediction time

Outcome resolution later appends exactly two rows, one for each benchmark.

Incomplete months must remain incomplete and must not be silently backfilled
using revised information.

## Transition definition

The persisted transition flag is defined as:

```text
actual_family != previous resolved month's actual_family
```

“One month before transition” and similar future-dependent labels must be
derived during reporting and must not be persisted with the original
prediction evidence.

## Probability contract

The canonical family order is:

1. `adverse_supply`
2. `benign_expansion`
3. `contraction`
4. `inflationary_expansion`
5. `mixed`

Each probability vector must:

- contain exactly these five families
- contain finite probabilities
- contain no negative values
- sum to 1.0 within a tolerance of `1e-10`
- use a log-loss floor of `1e-12`

Ranking fields and probability hashes must be derived from the validated
canonical vector.

## No-look-ahead contract

At prediction time:

- prediction timestamp must be on or after the information cutoff
- all source information cutoffs must be on or before the shadow information cutoff
- target outcome fields must be absent
- target availability must be later than the prediction timestamp
- latest-revised targets must not be read

At outcome resolution time:

- target availability must be on or before the resolution timestamp
- the persisted prediction must already exist
- the prediction row must not be modified
- the target must satisfy the fixed-horizon 90-day vintage contract

## Minimum evidence horizon

At least 12 complete prospective target months are required before any formal
comparative conclusion.

Before 12 complete months, the only permitted overall conclusion is:

```text
insufficient prospective evidence
```

## Allowed conclusions

- source advantage appears prospectively robust
- source advantage remains statistically inconclusive
- rolling frequency is not materially inferior
- insufficient prospective evidence

## Explicitly prohibited conclusions

- candidate approved
- production approved
- transition-aware switching approved
- source replaced
- comparator replaced

## Planned implementation phases

### Phase 0 — Frozen specification

Deliverables:

- `MODEL1D_v0.3.8_PLAN.md`

No executable code or database schema changes are permitted in this phase.

### Phase 1 — Persistence layer

Deliverables:

- DuckDB schema in `src/macropulse/data/repository.py`
- `save_macro_state_shadow_predictions()`
- `save_macro_state_shadow_outcomes()`
- schema tests
- append-only tests
- duplicate-protection tests
- no-look-ahead persistence tests

No runner, outcome resolver, or UI changes are permitted until Phase 1 tests
pass.

### Phase 2 — Prediction service

Deliverables:

- prospective shadow prediction engine
- source probability construction
- rolling-frequency probability construction
- monthly runner script
- prediction governance checks
- deterministic hashing
- service tests

### Phase 3 — Outcome resolution

Deliverables:

- fixed-horizon outcome resolver
- target-availability checks
- Brier and log-loss evaluation
- top-one/top-two/top-three evaluation
- transition classification
- append-only resolution tests

### Phase 4 — Monitoring and reporting

Deliverables:

- prospective evidence report
- stable/transition comparison
- unresolved-month register
- Streamlit shadow-monitoring panel
- minimum-evidence gate
- research-only release documentation

## Planned modules

```text
src/macropulse/macro_state/prospective_shadow.py
src/macropulse/macro_state/prospective_shadow_service.py
src/macropulse/macro_state/shadow_outcomes.py
src/macropulse/macro_state/shadow_outcomes_service.py
scripts/run_macro_state_prospective_shadow.py
scripts/resolve_macro_state_shadow_outcomes.py
tests/test_macro_state_shadow_schema.py
tests/test_macro_state_prospective_shadow.py
tests/test_macro_state_shadow_outcomes.py
tests/test_macro_state_shadow_governance.py
```

## Release boundary

Model 1D v0.3.8 is prospective monitoring infrastructure only.

It has no authority to:

- promote the frozen source
- promote rolling frequency
- select an adaptive policy
- construct a blended candidate
- merge Model 1D into production
- change the v0.3.6 source specification

Any later transition-aware candidate must be developed and evaluated in a
separate governed release after sufficient prospective evidence exists.
