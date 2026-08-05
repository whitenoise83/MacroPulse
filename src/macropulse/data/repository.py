from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

import duckdb
import pandas as pd

from macropulse.settings import settings


SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS series_metadata (
    series_id VARCHAR PRIMARY KEY,
    title VARCHAR,
    frequency VARCHAR,
    units VARCHAR,
    seasonal_adjustment VARCHAR,
    observation_start DATE,
    observation_end DATE,
    last_updated VARCHAR,
    source VARCHAR,
    loaded_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS observations (
    series_id VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    realtime_start DATE,
    realtime_end DATE,
    value DOUBLE,
    vintage_type VARCHAR NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_observations_series_date
ON observations(series_id, observation_date);

CREATE TABLE IF NOT EXISTS historical_snapshots (
    series_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    observation_date DATE NOT NULL,
    value DOUBLE,
    retrieved_at TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_historical_snapshots_lookup
ON historical_snapshots(as_of_date, series_id, observation_date);

CREATE TABLE IF NOT EXISTS snapshot_downloads (
    series_id VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    row_count INTEGER NOT NULL,
    downloaded_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS model_runs (
    run_id VARCHAR PRIMARY KEY,
    model_name VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    data_as_of DATE,
    target_period VARCHAR,
    status VARCHAR NOT NULL,
    metrics_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS forecasts (
    run_id VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    point_forecast DOUBLE,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS model_coefficients (
    run_id VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    feature VARCHAR NOT NULL,
    coefficient DOUBLE
);

CREATE TABLE IF NOT EXISTS backtest_runs (
    backtest_id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    target_series VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    forecast_frequency VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    config_json VARCHAR,
    metrics_json VARCHAR,
    skipped_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS backtest_results (
    backtest_id VARCHAR NOT NULL,
    forecast_date DATE NOT NULL,
    target_period VARCHAR NOT NULL,
    actual_release_date DATE,
    model_name VARCHAR NOT NULL,
    point_forecast DOUBLE,
    actual DOUBLE,
    error DOUBLE,
    abs_error DOUBLE,
    squared_error DOUBLE,
    direction_correct BOOLEAN,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    interval_covered BOOLEAN,
    imputed_feature_count INTEGER,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_backtest_results_id_date
ON backtest_results(backtest_id, forecast_date);

CREATE TABLE IF NOT EXISTS backtest_diagnostics (
    backtest_id VARCHAR NOT NULL,
    forecast_date DATE NOT NULL,
    target_period VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    converged BOOLEAN,
    iterations INTEGER,
    convergence_criterion DOUBLE,
    log_likelihood DOUBLE,
    details_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_backtest_diagnostics_id_date
ON backtest_diagnostics(backtest_id, forecast_date);

CREATE TABLE IF NOT EXISTS nowcast_information_sets (
    run_id VARCHAR NOT NULL,
    series_id VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    value DOUBLE,
    realtime_start DATE,
    realtime_end DATE,
    retrieved_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nowcast_information_sets_run
ON nowcast_information_sets(run_id, series_id, observation_date);

CREATE TABLE IF NOT EXISTS nowcast_news_runs (
    decomposition_id VARCHAR PRIMARY KEY,
    current_run_id VARCHAR NOT NULL,
    previous_run_id VARCHAR,
    target_period VARCHAR,
    status VARCHAR NOT NULL,
    previous_forecast DOUBLE,
    current_forecast DOUBLE,
    total_change DOUBLE,
    bridge_data_impact DOUBLE,
    bridge_refit_impact DOUBLE,
    dfm_news_impact DOUBLE,
    dfm_revision_impact DOUBLE,
    dfm_refit_impact DOUBLE,
    weight_change_impact DOUBLE,
    residual_interaction DOUBLE,
    details_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nowcast_news_runs_current
ON nowcast_news_runs(current_run_id, created_at);

CREATE TABLE IF NOT EXISTS nowcast_news_contributions (
    decomposition_id VARCHAR NOT NULL,
    contribution_type VARCHAR NOT NULL,
    model_name VARCHAR,
    series_id VARCHAR,
    observation_date DATE,
    previous_value DOUBLE,
    current_value DOUBLE,
    news DOUBLE,
    weight DOUBLE,
    impact DOUBLE,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nowcast_news_contributions_id
ON nowcast_news_contributions(decomposition_id, contribution_type);

CREATE TABLE IF NOT EXISTS nowcast_release_changes (
    decomposition_id VARCHAR NOT NULL,
    series_id VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    change_type VARCHAR NOT NULL,
    previous_value DOUBLE,
    current_value DOUBLE,
    value_change DOUBLE,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nowcast_release_changes_id
ON nowcast_release_changes(decomposition_id, series_id, observation_date);

CREATE TABLE IF NOT EXISTS release_calendar (
    series_id VARCHAR NOT NULL,
    release_id INTEGER NOT NULL,
    release_name VARCHAR NOT NULL,
    release_date DATE NOT NULL,
    release_last_updated VARCHAR,
    retrieved_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_release_calendar_date
ON release_calendar(release_date, series_id);

CREATE TABLE IF NOT EXISTS model_registry (
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    display_name VARCHAR NOT NULL,
    lifecycle_status VARCHAR NOT NULL,
    config_hash VARCHAR NOT NULL,
    code_hash VARCHAR NOT NULL,
    git_commit VARCHAR,
    registered_at TIMESTAMP NOT NULL,
    notes VARCHAR,
    PRIMARY KEY(model_id, model_version, config_hash, code_hash)
);

CREATE TABLE IF NOT EXISTS forecast_registry (
    run_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    config_hash VARCHAR NOT NULL,
    code_hash VARCHAR NOT NULL,
    git_commit VARCHAR,
    information_set_hash VARCHAR NOT NULL,
    information_cutoff DATE NOT NULL,
    data_as_of DATE,
    target_period VARCHAR NOT NULL,
    forecast_stage VARCHAR,
    champion_model VARCHAR NOT NULL,
    production_forecast DOUBLE,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    status VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS stage_backtest_runs (
    stage_backtest_id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR NOT NULL,
    config_json VARCHAR,
    metrics_json VARCHAR,
    notices_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS stage_backtest_results (
    stage_backtest_id VARCHAR NOT NULL,
    forecast_stage VARCHAR NOT NULL,
    forecast_date DATE NOT NULL,
    target_period VARCHAR NOT NULL,
    actual_release_date DATE,
    days_to_release INTEGER,
    model_name VARCHAR NOT NULL,
    point_forecast DOUBLE,
    actual DOUBLE,
    error DOUBLE,
    abs_error DOUBLE,
    squared_error DOUBLE,
    direction_correct BOOLEAN,
    raw_lower_80 DOUBLE,
    raw_upper_80 DOUBLE,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    interval_width DOUBLE,
    interval_covered BOOLEAN,
    interval_method VARCHAR,
    interval_history INTEGER,
    interval_details_json VARCHAR,
    imputed_feature_count INTEGER,
    information_set_hash VARCHAR,
    model_version VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stage_backtest_results_lookup
ON stage_backtest_results(stage_backtest_id, forecast_stage, forecast_date);

CREATE TABLE IF NOT EXISTS stage_backtest_diagnostics (
    stage_backtest_id VARCHAR NOT NULL,
    forecast_stage VARCHAR NOT NULL,
    forecast_date DATE NOT NULL,
    target_period VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    converged BOOLEAN,
    iterations INTEGER,
    details_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_runs (
    validation_id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    stage_backtest_id VARCHAR,
    quarter_backtest_id VARCHAR,
    status VARCHAR NOT NULL,
    passed_gates INTEGER NOT NULL,
    total_gates INTEGER NOT NULL,
    report_path VARCHAR,
    summary_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS validation_checks (
    validation_id VARCHAR NOT NULL,
    gate_name VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    observed_value VARCHAR,
    threshold VARCHAR,
    details_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_validation_checks_run
ON validation_checks(validation_id, gate_name, status);

CREATE TABLE IF NOT EXISTS model_approvals (
    approval_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    promoted_version VARCHAR NOT NULL,
    source_model_version VARCHAR NOT NULL,
    source_package_version VARCHAR,
    validation_id VARCHAR NOT NULL,
    validation_status VARCHAR NOT NULL,
    decision VARCHAR NOT NULL,
    approval_phrase VARCHAR NOT NULL,
    approved_at TIMESTAMP NOT NULL,
    freeze_assessment_report VARCHAR,
    recorded_at TIMESTAMP NOT NULL,
    notes VARCHAR
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_approvals_version
ON model_approvals(model_id, promoted_version);


CREATE TABLE IF NOT EXISTS inflation_model_runs (
    run_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL,
    data_as_of DATE,
    metrics_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS inflation_forecasts (
    run_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    point_forecast DOUBLE,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflation_forecasts_run
ON inflation_forecasts(run_id, target_series);

CREATE TABLE IF NOT EXISTS inflation_coefficients (
    run_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    feature VARCHAR NOT NULL,
    coefficient DOUBLE
);

CREATE TABLE IF NOT EXISTS inflation_backtest_runs (
    backtest_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    start_period VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    method VARCHAR NOT NULL,
    metrics_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS inflation_backtest_results (
    backtest_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    point_forecast DOUBLE,
    actual DOUBLE,
    error DOUBLE,
    abs_error DOUBLE,
    squared_error DOUBLE,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    interval_covered BOOLEAN,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflation_backtest_results
ON inflation_backtest_results(backtest_id, target_series, target_period);

CREATE TABLE IF NOT EXISTS inflation_vintage_backtest_runs (
    backtest_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    start_period VARCHAR NOT NULL,
    end_period VARCHAR,
    target_series_json VARCHAR NOT NULL,
    stages_json VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    config_json VARCHAR,
    metrics_json VARCHAR,
    notices_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS inflation_vintage_backtest_results (
    backtest_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    forecast_stage VARCHAR NOT NULL,
    forecast_date DATE NOT NULL,
    target_period VARCHAR NOT NULL,
    actual_release_date DATE,
    days_to_release INTEGER,
    model_name VARCHAR NOT NULL,
    point_forecast DOUBLE,
    actual DOUBLE,
    error DOUBLE,
    abs_error DOUBLE,
    squared_error DOUBLE,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    interval_covered BOOLEAN,
    imputed_feature_count INTEGER,
    information_set_hash VARCHAR,
    max_observation_date DATE,
    training_observations INTEGER,
    target_leakage BOOLEAN,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflation_vintage_results
ON inflation_vintage_backtest_results(backtest_id, target_series, forecast_stage, target_period);


CREATE TABLE IF NOT EXISTS inflation_interval_calibration_runs (
    calibration_id VARCHAR PRIMARY KEY,
    backtest_id VARCHAR NOT NULL,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    method VARCHAR NOT NULL,
    target_coverage DOUBLE NOT NULL,
    minimum_prior_errors INTEGER NOT NULL,
    rolling_window INTEGER,
    status VARCHAR NOT NULL,
    metrics_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS inflation_interval_calibrated_results (
    calibration_id VARCHAR NOT NULL,
    backtest_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    forecast_stage VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    interval_covered BOOLEAN,
    interval_half_width DOUBLE,
    prior_error_count INTEGER NOT NULL,
    calibration_window_count INTEGER NOT NULL,
    calibration_cutoff_period VARCHAR,
    calibration_status VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflation_interval_calibration
ON inflation_interval_calibrated_results(
    calibration_id, target_series, forecast_stage, target_period, model_name
);

CREATE TABLE IF NOT EXISTS inflation_validation_runs (
    validation_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    backtest_id VARCHAR,
    created_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL,
    passed_checks INTEGER NOT NULL,
    failed_checks INTEGER NOT NULL,
    warnings INTEGER NOT NULL,
    report_path VARCHAR,
    summary_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS inflation_validation_checks (
    validation_id VARCHAR NOT NULL,
    gate_name VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    observed_value VARCHAR,
    threshold VARCHAR,
    details_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflation_validation_checks
ON inflation_validation_checks(validation_id, gate_name, status);

CREATE TABLE IF NOT EXISTS inflation_live_runs (
    run_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    information_cutoff DATE NOT NULL,
    data_as_of DATE,
    status VARCHAR NOT NULL,
    candidate_validation_id VARCHAR NOT NULL,
    backtest_id VARCHAR NOT NULL,
    config_hash VARCHAR NOT NULL,
    code_hash VARCHAR NOT NULL,
    git_commit VARCHAR,
    information_set_hash VARCHAR NOT NULL,
    model_state_hash VARCHAR NOT NULL,
    governance_signature VARCHAR NOT NULL,
    metrics_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS inflation_live_forecasts (
    run_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    forecast_stage VARCHAR NOT NULL,
    information_cutoff DATE NOT NULL,
    estimated_release_date DATE,
    stable_model_name VARCHAR NOT NULL,
    stable_point_forecast DOUBLE,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    interval_half_width DOUBLE,
    interval_method VARCHAR NOT NULL,
    interval_prior_errors INTEGER NOT NULL,
    interval_cutoff_period VARCHAR,
    shadow_model_name VARCHAR NOT NULL,
    shadow_point_forecast DOUBLE,
    shadow_selection_reason VARCHAR,
    shadow_prior_errors INTEGER,
    latest_observed_period VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_inflation_live_forecasts_unique
ON inflation_live_forecasts(run_id, target_series);

CREATE TABLE IF NOT EXISTS inflation_live_components (
    run_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    forecast_stage VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    point_forecast DOUBLE,
    raw_lower_80 DOUBLE,
    raw_upper_80 DOUBLE,
    role VARCHAR NOT NULL,
    diagnostics_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflation_live_components
ON inflation_live_components(run_id, target_series, model_name);

CREATE TABLE IF NOT EXISTS inflation_live_information_sets (
    run_id VARCHAR NOT NULL,
    series_id VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    value DOUBLE,
    realtime_start DATE,
    realtime_end DATE,
    retrieved_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflation_live_information_sets
ON inflation_live_information_sets(run_id, series_id, observation_date);

CREATE TABLE IF NOT EXISTS inflation_news_runs (
    decomposition_id VARCHAR PRIMARY KEY,
    current_run_id VARCHAR NOT NULL,
    previous_run_id VARCHAR,
    target_series VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    previous_forecast DOUBLE,
    current_forecast DOUBLE,
    total_change DOUBLE,
    new_data_impact DOUBLE,
    revision_impact DOUBLE,
    model_refit_impact DOUBLE,
    policy_change_impact DOUBLE,
    residual_interaction DOUBLE,
    details_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflation_news_runs_current
ON inflation_news_runs(current_run_id, target_series);

CREATE TABLE IF NOT EXISTS inflation_news_contributions (
    decomposition_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    contribution_type VARCHAR NOT NULL,
    model_name VARCHAR,
    series_id VARCHAR,
    impact DOUBLE,
    details_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflation_news_contributions
ON inflation_news_contributions(decomposition_id, contribution_type, series_id);

CREATE TABLE IF NOT EXISTS inflation_release_changes (
    decomposition_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    series_id VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    change_type VARCHAR NOT NULL,
    previous_value DOUBLE,
    current_value DOUBLE,
    value_change DOUBLE,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflation_release_changes
ON inflation_release_changes(decomposition_id, series_id, observation_date);

CREATE TABLE IF NOT EXISTS labour_model_runs (
    run_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL,
    data_as_of DATE,
    metrics_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS labour_forecasts (
    run_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    target_unit VARCHAR NOT NULL,
    display_decimals INTEGER NOT NULL,
    target_period VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    point_forecast DOUBLE,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    diagnostics_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_labour_forecasts_run
ON labour_forecasts(run_id, target_series);

CREATE TABLE IF NOT EXISTS labour_coefficients (
    run_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    feature VARCHAR NOT NULL,
    coefficient DOUBLE
);

CREATE TABLE IF NOT EXISTS labour_backtest_runs (
    backtest_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    start_period VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    method VARCHAR NOT NULL,
    metrics_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS labour_backtest_results (
    backtest_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    target_unit VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    point_forecast DOUBLE,
    actual DOUBLE,
    error DOUBLE,
    abs_error DOUBLE,
    squared_error DOUBLE,
    direction_correct BOOLEAN,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    interval_covered BOOLEAN,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_labour_backtest_results
ON labour_backtest_results(backtest_id, target_series, target_period);

CREATE TABLE IF NOT EXISTS labour_vintage_backtest_runs (
    backtest_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    start_period VARCHAR NOT NULL,
    end_period VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    stage_codes_json VARCHAR,
    target_series_json VARCHAR,
    metrics_json VARCHAR,
    notices_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS labour_vintage_backtest_results (
    backtest_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    target_unit VARCHAR NOT NULL,
    forecast_stage VARCHAR NOT NULL,
    forecast_date DATE NOT NULL,
    target_period VARCHAR NOT NULL,
    actual_release_date DATE NOT NULL,
    days_to_release INTEGER NOT NULL,
    model_name VARCHAR NOT NULL,
    point_forecast DOUBLE,
    actual DOUBLE,
    error DOUBLE,
    abs_error DOUBLE,
    squared_error DOUBLE,
    direction_correct BOOLEAN,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    interval_covered BOOLEAN,
    training_observations INTEGER,
    imputed_feature_count INTEGER,
    information_set_hash VARCHAR,
    target_leakage BOOLEAN,
    max_observation_date DATE,
    regime VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_labour_vintage_results
ON labour_vintage_backtest_results(backtest_id, target_series, forecast_stage, target_period);

CREATE TABLE IF NOT EXISTS labour_interval_calibration_runs (
    calibration_id VARCHAR PRIMARY KEY,
    backtest_id VARCHAR NOT NULL,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    method VARCHAR NOT NULL,
    target_coverage DOUBLE NOT NULL,
    minimum_prior_errors INTEGER NOT NULL,
    rolling_window INTEGER NOT NULL,
    decay DOUBLE NOT NULL,
    status VARCHAR NOT NULL,
    metrics_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS labour_interval_calibrated_results (
    calibration_id VARCHAR NOT NULL,
    backtest_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    forecast_stage VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    interval_method VARCHAR NOT NULL,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    interval_covered BOOLEAN,
    interval_half_width DOUBLE,
    interval_score DOUBLE,
    prior_error_count INTEGER NOT NULL,
    calibration_window_count INTEGER NOT NULL,
    calibration_cutoff_period VARCHAR,
    calibration_status VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_labour_interval_calibration
ON labour_interval_calibrated_results(
    calibration_id, target_series, forecast_stage, target_period, model_name
);

CREATE TABLE IF NOT EXISTS labour_validation_runs (
    validation_id VARCHAR PRIMARY KEY,
    backtest_id VARCHAR NOT NULL,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL,
    passed_gates INTEGER NOT NULL,
    failed_gates INTEGER NOT NULL,
    warning_gates INTEGER NOT NULL,
    report_path VARCHAR,
    summary_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS labour_validation_checks (
    validation_id VARCHAR NOT NULL,
    gate_name VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    observed_value VARCHAR,
    threshold VARCHAR,
    details_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_labour_validation_checks
ON labour_validation_checks(validation_id, gate_name, status);

CREATE TABLE IF NOT EXISTS labour_live_runs (
    run_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    information_cutoff DATE NOT NULL,
    data_as_of DATE,
    status VARCHAR NOT NULL,
    candidate_validation_id VARCHAR NOT NULL,
    backtest_id VARCHAR NOT NULL,
    config_hash VARCHAR NOT NULL,
    code_hash VARCHAR NOT NULL,
    git_commit VARCHAR,
    information_set_hash VARCHAR NOT NULL,
    model_state_hash VARCHAR NOT NULL,
    governance_signature VARCHAR NOT NULL,
    metrics_json VARCHAR,
    notes VARCHAR
);

CREATE TABLE IF NOT EXISTS labour_live_forecasts (
    run_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    target_unit VARCHAR NOT NULL,
    display_decimals INTEGER NOT NULL,
    target_period VARCHAR NOT NULL,
    forecast_stage VARCHAR NOT NULL,
    information_cutoff DATE NOT NULL,
    estimated_release_date DATE,
    stable_model_name VARCHAR NOT NULL,
    stable_point_forecast DOUBLE,
    lower_80 DOUBLE,
    upper_80 DOUBLE,
    interval_half_width DOUBLE,
    interval_method VARCHAR NOT NULL,
    interval_prior_errors INTEGER NOT NULL,
    interval_cutoff_period VARCHAR,
    shadow_model_name VARCHAR NOT NULL,
    shadow_point_forecast DOUBLE,
    shadow_selection_reason VARCHAR,
    shadow_prior_errors INTEGER,
    latest_observed_period VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_labour_live_forecasts_unique
ON labour_live_forecasts(run_id, target_series);

CREATE TABLE IF NOT EXISTS labour_live_components (
    run_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    target_unit VARCHAR NOT NULL,
    display_decimals INTEGER NOT NULL,
    target_period VARCHAR NOT NULL,
    forecast_stage VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    point_forecast DOUBLE,
    raw_lower_80 DOUBLE,
    raw_upper_80 DOUBLE,
    role VARCHAR NOT NULL,
    diagnostics_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_labour_live_components
ON labour_live_components(run_id, target_series, model_name);

CREATE TABLE IF NOT EXISTS labour_live_information_sets (
    run_id VARCHAR NOT NULL,
    series_id VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    value DOUBLE,
    realtime_start DATE,
    realtime_end DATE,
    retrieved_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_labour_live_information_sets
ON labour_live_information_sets(run_id, series_id, observation_date);

CREATE TABLE IF NOT EXISTS labour_news_runs (
    decomposition_id VARCHAR PRIMARY KEY,
    current_run_id VARCHAR NOT NULL,
    previous_run_id VARCHAR,
    target_series VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    previous_forecast DOUBLE,
    current_forecast DOUBLE,
    total_change DOUBLE,
    new_data_impact DOUBLE,
    revision_impact DOUBLE,
    model_refit_impact DOUBLE,
    policy_change_impact DOUBLE,
    residual_interaction DOUBLE,
    details_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_labour_news_runs_current
ON labour_news_runs(current_run_id, target_series);

CREATE TABLE IF NOT EXISTS labour_news_contributions (
    decomposition_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    contribution_type VARCHAR NOT NULL,
    model_name VARCHAR,
    series_id VARCHAR,
    impact DOUBLE,
    details_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_labour_news_contributions
ON labour_news_contributions(decomposition_id, contribution_type, series_id);

CREATE TABLE IF NOT EXISTS labour_release_changes (
    decomposition_id VARCHAR NOT NULL,
    target_series VARCHAR NOT NULL,
    series_id VARCHAR NOT NULL,
    observation_date DATE NOT NULL,
    change_type VARCHAR NOT NULL,
    previous_value DOUBLE,
    current_value DOUBLE,
    value_change DOUBLE,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_labour_release_changes
ON labour_release_changes(decomposition_id, series_id, observation_date);


CREATE TABLE IF NOT EXISTS macro_state_runs (
    run_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    state_as_of DATE NOT NULL,
    status VARCHAR NOT NULL,
    primary_regime VARCHAR NOT NULL,
    overall_confidence DOUBLE NOT NULL,
    gdp_run_id VARCHAR NOT NULL,
    inflation_run_id VARCHAR NOT NULL,
    labour_run_id VARCHAR NOT NULL,
    oldest_source_cutoff DATE NOT NULL,
    newest_source_cutoff DATE NOT NULL,
    cutoff_spread_days INTEGER NOT NULL,
    config_hash VARCHAR NOT NULL,
    code_hash VARCHAR NOT NULL,
    git_commit VARCHAR,
    source_bundle_hash VARCHAR NOT NULL,
    state_hash VARCHAR NOT NULL,
    metrics_json VARCHAR,
    notes VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_macro_state_runs_as_of
ON macro_state_runs(state_as_of, run_timestamp);

CREATE TABLE IF NOT EXISTS macro_state_dimensions (
    run_id VARCHAR NOT NULL,
    dimension VARCHAR NOT NULL,
    score DOUBLE NOT NULL,
    lower_score DOUBLE NOT NULL,
    upper_score DOUBLE NOT NULL,
    label VARCHAR NOT NULL,
    confidence DOUBLE NOT NULL,
    previous_run_id VARCHAR,
    previous_score DOUBLE,
    delta_score DOUBLE,
    details_json VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_state_dimensions_unique
ON macro_state_dimensions(run_id, dimension);

CREATE TABLE IF NOT EXISTS macro_state_inputs (
    run_id VARCHAR NOT NULL,
    source_model_id VARCHAR NOT NULL,
    source_model_version VARCHAR NOT NULL,
    source_run_id VARCHAR NOT NULL,
    source_target VARCHAR NOT NULL,
    source_target_name VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    forecast_stage VARCHAR,
    point_forecast DOUBLE NOT NULL,
    lower_80 DOUBLE NOT NULL,
    upper_80 DOUBLE NOT NULL,
    information_cutoff DATE NOT NULL,
    data_as_of DATE,
    source_hash VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_macro_state_inputs_run
ON macro_state_inputs(run_id, source_model_id, source_target);

CREATE TABLE IF NOT EXISTS macro_state_regimes (
    run_id VARCHAR NOT NULL,
    regime_code VARCHAR NOT NULL,
    regime_label VARCHAR NOT NULL,
    is_primary BOOLEAN NOT NULL,
    rule_strength DOUBLE NOT NULL,
    rationale VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_macro_state_regimes_run
ON macro_state_regimes(run_id, is_primary);


CREATE TABLE IF NOT EXISTS macro_state_history_runs (
    reconstruction_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    months_requested INTEGER NOT NULL,
    months_reconstructed INTEGER NOT NULL,
    no_look_ahead_pass BOOLEAN NOT NULL,
    config_hash VARCHAR NOT NULL,
    code_hash VARCHAR NOT NULL,
    git_commit VARCHAR,
    created_at TIMESTAMP NOT NULL,
    notes VARCHAR
);


ALTER TABLE macro_state_history_runs
ADD COLUMN IF NOT EXISTS source_mode VARCHAR;

ALTER TABLE macro_state_history_runs
ADD COLUMN IF NOT EXISTS gdp_source_id VARCHAR;

ALTER TABLE macro_state_history_runs
ADD COLUMN IF NOT EXISTS inflation_source_id VARCHAR;

ALTER TABLE macro_state_history_runs
ADD COLUMN IF NOT EXISTS labour_source_id VARCHAR;

ALTER TABLE macro_state_history_runs
ADD COLUMN IF NOT EXISTS coverage_ratio DOUBLE;

ALTER TABLE macro_state_history_runs
ADD COLUMN IF NOT EXISTS longest_contiguous_months INTEGER;

CREATE TABLE IF NOT EXISTS macro_state_history_states (
    reconstruction_id VARCHAR NOT NULL,
    state_date DATE NOT NULL,
    growth_score DOUBLE NOT NULL,
    inflation_score DOUBLE NOT NULL,
    labour_score DOUBLE NOT NULL,
    growth_lower DOUBLE NOT NULL,
    growth_upper DOUBLE NOT NULL,
    inflation_lower DOUBLE NOT NULL,
    inflation_upper DOUBLE NOT NULL,
    labour_lower DOUBLE NOT NULL,
    labour_upper DOUBLE NOT NULL,
    growth_label VARCHAR NOT NULL,
    inflation_label VARCHAR NOT NULL,
    labour_label VARCHAR NOT NULL,
    primary_regime VARCHAR NOT NULL,
    primary_regime_label VARCHAR NOT NULL,
    primary_regime_strength DOUBLE NOT NULL,
    possible_regimes_json VARCHAR NOT NULL,
    possible_regime_count INTEGER NOT NULL,
    source_cutoff_spread_days INTEGER NOT NULL,
    no_look_ahead_pass BOOLEAN NOT NULL,
    source_bundle_hash VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_state_history_state_unique
ON macro_state_history_states(reconstruction_id, state_date);

CREATE TABLE IF NOT EXISTS macro_state_history_inputs (
    reconstruction_id VARCHAR NOT NULL,
    state_date DATE NOT NULL,
    source_model_id VARCHAR NOT NULL,
    source_model_version VARCHAR NOT NULL,
    source_run_id VARCHAR NOT NULL,
    source_target VARCHAR NOT NULL,
    source_target_name VARCHAR NOT NULL,
    target_period VARCHAR NOT NULL,
    forecast_stage VARCHAR,
    point_forecast DOUBLE NOT NULL,
    lower_80 DOUBLE NOT NULL,
    upper_80 DOUBLE NOT NULL,
    information_cutoff DATE NOT NULL,
    data_as_of DATE,
    source_hash VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_macro_state_history_inputs
ON macro_state_history_inputs(reconstruction_id, state_date);


ALTER TABLE macro_state_history_inputs
ADD COLUMN IF NOT EXISTS source_validation_id VARCHAR;

ALTER TABLE macro_state_history_inputs
ADD COLUMN IF NOT EXISTS interval_source VARCHAR;

ALTER TABLE macro_state_history_inputs
ADD COLUMN IF NOT EXISTS actual_release_date DATE;

ALTER TABLE macro_state_history_inputs
ADD COLUMN IF NOT EXISTS target_leakage BOOLEAN;

ALTER TABLE macro_state_history_inputs
ADD COLUMN IF NOT EXISTS max_observation_date DATE;

ALTER TABLE macro_state_history_inputs
ADD COLUMN IF NOT EXISTS model_name VARCHAR;

ALTER TABLE macro_state_history_inputs
ADD COLUMN IF NOT EXISTS information_set_hash VARCHAR;


CREATE TABLE IF NOT EXISTS macro_state_history_durations (
    reconstruction_id VARCHAR NOT NULL,
    primary_regime VARCHAR NOT NULL,
    primary_regime_label VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    months INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS macro_state_history_transitions (
    reconstruction_id VARCHAR NOT NULL,
    from_regime VARCHAR NOT NULL,
    to_regime VARCHAR NOT NULL,
    transition_probability DOUBLE NOT NULL,
    created_at TIMESTAMP NOT NULL
);


CREATE TABLE IF NOT EXISTS macro_state_tournament_runs (
    tournament_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    reconstruction_id VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL,
    training_start DATE NOT NULL,
    training_end DATE NOT NULL,
    validation_start DATE NOT NULL,
    validation_end DATE NOT NULL,
    holdout_start DATE NOT NULL,
    holdout_end DATE NOT NULL,
    training_months INTEGER NOT NULL,
    validation_months INTEGER NOT NULL,
    holdout_months INTEGER NOT NULL,
    core_candidates INTEGER NOT NULL,
    uncertainty_candidates INTEGER NOT NULL,
    selected_candidate_id VARCHAR NOT NULL,
    selected_core_candidate_id VARCHAR NOT NULL,
    selected_validation_score DOUBLE NOT NULL,
    selected_holdout_rank INTEGER,
    config_hash VARCHAR NOT NULL,
    code_hash VARCHAR NOT NULL,
    git_commit VARCHAR,
    baseline_metrics_json VARCHAR NOT NULL,
    metrics_json VARCHAR NOT NULL,
    report_path VARCHAR,
    notes VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_macro_state_tournament_runs
ON macro_state_tournament_runs(created_at, status);

CREATE TABLE IF NOT EXISTS macro_state_tournament_candidates (
    tournament_id VARCHAR NOT NULL,
    candidate_id VARCHAR NOT NULL,
    candidate_type VARCHAR NOT NULL,
    core_candidate_id VARCHAR NOT NULL,
    normalization_id VARCHAR NOT NULL,
    inflation_weights_id VARCHAR NOT NULL,
    labour_weights_id VARCHAR NOT NULL,
    threshold_id VARCHAR NOT NULL,
    uncertainty_id VARCHAR,
    selected BOOLEAN NOT NULL,
    validation_rank INTEGER,
    holdout_rank INTEGER,
    validation_score DOUBLE,
    holdout_score DOUBLE,
    config_json VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_state_tournament_candidate_unique
ON macro_state_tournament_candidates(tournament_id, candidate_id);

CREATE TABLE IF NOT EXISTS macro_state_tournament_metrics (
    tournament_id VARCHAR NOT NULL,
    candidate_id VARCHAR NOT NULL,
    split VARCHAR NOT NULL,
    months INTEGER NOT NULL,
    dimension_rmse DOUBLE,
    dimension_mae DOUBLE,
    exact_regime_accuracy DOUBLE,
    family_accuracy DOUBLE,
    sign_accuracy DOUBLE,
    forecast_churn DOUBLE,
    actual_churn DOUBLE,
    churn_gap DOUBLE,
    distribution_jsd DOUBLE,
    forecast_regime_entropy DOUBLE,
    actual_regime_entropy DOUBLE,
    regime_collapse_penalty DOUBLE,
    forecast_regime_count INTEGER,
    actual_regime_count INTEGER,
    brier_score DOUBLE,
    log_loss DOUBLE,
    coverage_80 DOUBLE,
    coverage_gap DOUBLE,
    mean_top_probability DOUBLE,
    mean_effective_regimes DOUBLE,
    top1_accuracy DOUBLE,
    core_score DOUBLE,
    uncertainty_score DOUBLE,
    final_score DOUBLE,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_macro_state_tournament_metrics
ON macro_state_tournament_metrics(tournament_id, candidate_id, split);

CREATE TABLE IF NOT EXISTS macro_state_tournament_monthly (
    tournament_id VARCHAR NOT NULL,
    candidate_id VARCHAR NOT NULL,
    core_candidate_id VARCHAR NOT NULL,
    uncertainty_id VARCHAR NOT NULL,
    state_date DATE NOT NULL,
    split VARCHAR NOT NULL,
    forecast_growth DOUBLE NOT NULL,
    forecast_inflation DOUBLE NOT NULL,
    forecast_labour DOUBLE NOT NULL,
    actual_growth DOUBLE NOT NULL,
    actual_inflation DOUBLE NOT NULL,
    actual_labour DOUBLE NOT NULL,
    growth_lower DOUBLE NOT NULL,
    growth_upper DOUBLE NOT NULL,
    inflation_lower DOUBLE NOT NULL,
    inflation_upper DOUBLE NOT NULL,
    labour_lower DOUBLE NOT NULL,
    labour_upper DOUBLE NOT NULL,
    forecast_regime VARCHAR NOT NULL,
    actual_regime VARCHAR NOT NULL,
    top_regime VARCHAR NOT NULL,
    top_probability DOUBLE NOT NULL,
    actual_regime_probability DOUBLE NOT NULL,
    brier_score DOUBLE NOT NULL,
    log_loss DOUBLE NOT NULL,
    coverage_80 BOOLEAN NOT NULL,
    effective_regimes DOUBLE NOT NULL,
    probabilities_json VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_macro_state_tournament_monthly
ON macro_state_tournament_monthly(tournament_id, candidate_id, state_date);

CREATE TABLE IF NOT EXISTS macro_state_stability_runs (
    stability_id VARCHAR PRIMARY KEY,
    model_id VARCHAR NOT NULL,
    model_version VARCHAR NOT NULL,
    reconstruction_id VARCHAR NOT NULL,
    source_tournament_id VARCHAR,
    created_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL,
    fold_count INTEGER NOT NULL,
    selection_start DATE NOT NULL,
    selection_end DATE NOT NULL,
    selection_months INTEGER NOT NULL,
    audit_start DATE NOT NULL,
    audit_end DATE NOT NULL,
    audit_months INTEGER NOT NULL,
    core_candidates INTEGER NOT NULL,
    final_candidates INTEGER NOT NULL,
    selected_candidate_id VARCHAR NOT NULL,
    selected_core_candidate_id VARCHAR NOT NULL,
    selected_uncertainty_id VARCHAR NOT NULL,
    selected_stability_score DOUBLE NOT NULL,
    selected_stability_rank INTEGER NOT NULL,
    selected_governance_pass BOOLEAN NOT NULL,
    selected_audit_rank INTEGER,
    config_hash VARCHAR NOT NULL,
    code_hash VARCHAR NOT NULL,
    git_commit VARCHAR,
    warnings_json VARCHAR NOT NULL,
    report_path VARCHAR,
    notes VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_macro_state_stability_runs
ON macro_state_stability_runs(created_at, status);

CREATE TABLE IF NOT EXISTS macro_state_stability_folds (
    stability_id VARCHAR NOT NULL,
    fold_id VARCHAR NOT NULL,
    training_start DATE NOT NULL,
    training_end DATE NOT NULL,
    training_months INTEGER NOT NULL,
    evaluation_start DATE NOT NULL,
    evaluation_end DATE NOT NULL,
    evaluation_months INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_state_stability_folds
ON macro_state_stability_folds(stability_id, fold_id);

CREATE TABLE IF NOT EXISTS macro_state_stability_candidates (
    stability_id VARCHAR NOT NULL,
    candidate_id VARCHAR NOT NULL,
    candidate_type VARCHAR NOT NULL,
    core_candidate_id VARCHAR NOT NULL,
    uncertainty_id VARCHAR,
    selected BOOLEAN NOT NULL,
    governance_pass BOOLEAN NOT NULL,
    stability_rank INTEGER NOT NULL,
    stability_score DOUBLE NOT NULL,
    folds INTEGER NOT NULL,
    mean_fold_score DOUBLE NOT NULL,
    median_fold_score DOUBLE NOT NULL,
    mean_fold_rank DOUBLE NOT NULL,
    median_fold_rank DOUBLE NOT NULL,
    rank_std DOUBLE NOT NULL,
    best_fold_rank INTEGER NOT NULL,
    worst_fold_rank INTEGER NOT NULL,
    fold_win_rate DOUBLE NOT NULL,
    leading_third_rate DOUBLE NOT NULL,
    catastrophic_fold_count INTEGER NOT NULL,
    baseline_dominance_rate DOUBLE NOT NULL,
    mean_baseline_margin DOUBLE NOT NULL,
    average_regret DOUBLE NOT NULL,
    regime_collapse_fold_rate DOUBLE NOT NULL,
    uncertainty_method_win_rate DOUBLE,
    proper_score_dominance_rate DOUBLE,
    bootstrap_margin_mean DOUBLE,
    bootstrap_margin_lower DOUBLE,
    bootstrap_margin_upper DOUBLE,
    audit_final_score DOUBLE,
    audit_final_rank INTEGER,
    audit_exact_regime_accuracy DOUBLE,
    audit_brier_score DOUBLE,
    audit_log_loss DOUBLE,
    audit_coverage_80 DOUBLE,
    audit_top1_accuracy DOUBLE,
    audit_baseline_margin DOUBLE,
    metrics_json VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_state_stability_candidates
ON macro_state_stability_candidates(stability_id, candidate_id);

CREATE TABLE IF NOT EXISTS macro_state_stability_fold_metrics (
    stability_id VARCHAR NOT NULL,
    fold_id VARCHAR NOT NULL,
    candidate_id VARCHAR NOT NULL,
    candidate_type VARCHAR NOT NULL,
    core_candidate_id VARCHAR NOT NULL,
    uncertainty_id VARCHAR,
    evaluation_start DATE NOT NULL,
    evaluation_end DATE NOT NULL,
    evaluation_months INTEGER NOT NULL,
    score DOUBLE NOT NULL,
    rank INTEGER NOT NULL,
    core_score DOUBLE,
    uncertainty_score DOUBLE,
    dimension_rmse DOUBLE,
    exact_regime_accuracy DOUBLE,
    family_accuracy DOUBLE,
    sign_accuracy DOUBLE,
    regime_collapse_penalty DOUBLE,
    brier_score DOUBLE,
    log_loss DOUBLE,
    coverage_80 DOUBLE,
    top1_accuracy DOUBLE,
    mode_accuracy DOUBLE,
    persistence_accuracy DOUBLE,
    strongest_baseline VARCHAR,
    strongest_baseline_accuracy DOUBLE,
    baseline_margin DOUBLE,
    beats_strongest_baseline BOOLEAN,
    uncertainty_method_rank INTEGER,
    proper_score_improvement DOUBLE,
    proper_score_dominates BOOLEAN,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_macro_state_stability_fold_metrics
ON macro_state_stability_fold_metrics(stability_id, fold_id, candidate_id);

CREATE TABLE IF NOT EXISTS macro_state_stability_audit_metrics (
    stability_id VARCHAR NOT NULL,
    candidate_id VARCHAR NOT NULL,
    core_candidate_id VARCHAR NOT NULL,
    uncertainty_id VARCHAR NOT NULL,
    audit_final_score DOUBLE NOT NULL,
    audit_final_rank INTEGER NOT NULL,
    audit_core_score DOUBLE NOT NULL,
    audit_core_rank INTEGER NOT NULL,
    audit_uncertainty_score DOUBLE NOT NULL,
    audit_uncertainty_rank INTEGER NOT NULL,
    audit_exact_regime_accuracy DOUBLE NOT NULL,
    audit_family_accuracy DOUBLE NOT NULL,
    audit_sign_accuracy DOUBLE NOT NULL,
    audit_dimension_rmse DOUBLE NOT NULL,
    audit_regime_collapse_penalty DOUBLE NOT NULL,
    audit_brier_score DOUBLE NOT NULL,
    audit_log_loss DOUBLE NOT NULL,
    audit_coverage_80 DOUBLE NOT NULL,
    audit_top1_accuracy DOUBLE NOT NULL,
    audit_mean_effective_regimes DOUBLE NOT NULL,
    audit_baseline_accuracy DOUBLE NOT NULL,
    audit_baseline_margin DOUBLE NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_macro_state_stability_audit
ON macro_state_stability_audit_metrics(stability_id, audit_final_rank);

CREATE TABLE IF NOT EXISTS macro_state_stability_subperiod_metrics (
    stability_id VARCHAR NOT NULL,
    candidate_id VARCHAR NOT NULL,
    subperiod_id VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    months INTEGER NOT NULL,
    dimension_rmse DOUBLE NOT NULL,
    exact_regime_accuracy DOUBLE NOT NULL,
    family_accuracy DOUBLE NOT NULL,
    sign_accuracy DOUBLE NOT NULL,
    regime_collapse_penalty DOUBLE NOT NULL,
    brier_score DOUBLE NOT NULL,
    log_loss DOUBLE NOT NULL,
    coverage_80 DOUBLE NOT NULL,
    top1_accuracy DOUBLE NOT NULL,
    mean_effective_regimes DOUBLE NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_macro_state_stability_subperiod
ON macro_state_stability_subperiod_metrics(
    stability_id, candidate_id, subperiod_id
);

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

'''


class MacroRepository:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or settings.database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self, read_only: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
        connection = duckdb.connect(str(self.database_path), read_only=read_only)
        try:
            yield connection
        finally:
            connection.close()

    def initialise(self) -> None:
        with self.connect() as connection:
            connection.execute(SCHEMA_SQL)

    def upsert_metadata(self, metadata: dict) -> None:
        frame = pd.DataFrame(
            [
                {
                    "series_id": metadata.get("id"),
                    "title": metadata.get("title"),
                    "frequency": metadata.get("frequency"),
                    "units": metadata.get("units"),
                    "seasonal_adjustment": metadata.get("seasonal_adjustment"),
                    "observation_start": metadata.get("observation_start"),
                    "observation_end": metadata.get("observation_end"),
                    "last_updated": metadata.get("last_updated"),
                    "source": "FRED",
                    "loaded_at": pd.Timestamp.now(tz="UTC").tz_localize(None),
                }
            ]
        )
        with self.connect() as connection:
            connection.register("_metadata", frame)
            connection.execute(
                "DELETE FROM series_metadata WHERE series_id IN "
                "(SELECT series_id FROM _metadata)"
            )
            connection.execute("INSERT INTO series_metadata SELECT * FROM _metadata")
            connection.unregister("_metadata")

    def upsert_observations(self, frame: pd.DataFrame) -> int:
        if frame.empty:
            return 0

        with self.connect() as connection:
            connection.register("_incoming", frame)
            connection.execute(
                '''
                DELETE FROM observations AS existing
                WHERE EXISTS (
                    SELECT 1
                    FROM _incoming AS incoming
                    WHERE existing.series_id = incoming.series_id
                      AND existing.observation_date = incoming.observation_date
                      AND COALESCE(existing.realtime_start, DATE '1900-01-01')
                          = COALESCE(incoming.realtime_start, DATE '1900-01-01')
                      AND existing.vintage_type = incoming.vintage_type
                )
                '''
            )
            connection.execute(
                '''
                INSERT INTO observations
                SELECT series_id, observation_date, realtime_start, realtime_end,
                       value, vintage_type, retrieved_at, source
                FROM _incoming
                '''
            )
            connection.unregister("_incoming")
        return len(frame)

    def latest_observations(self, series_ids: list[str] | None = None) -> pd.DataFrame:
        where_clause = "WHERE vintage_type = 'latest'"
        parameters: list = []
        if series_ids:
            placeholders = ", ".join(["?"] * len(series_ids))
            where_clause += f" AND series_id IN ({placeholders})"
            parameters.extend(series_ids)

        query = f'''
        SELECT series_id, observation_date, value, realtime_start, realtime_end,
               retrieved_at
        FROM observations
        {where_clause}
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY series_id, observation_date
            ORDER BY retrieved_at DESC
        ) = 1
        ORDER BY series_id, observation_date
        '''
        with self.connect(read_only=True) as connection:
            return connection.execute(query, parameters).fetchdf()

    def snapshot_is_cached(self, series_id: str, as_of_date: date) -> bool:
        query = '''
        SELECT COUNT(*)
        FROM snapshot_downloads
        WHERE series_id = ? AND as_of_date = ? AND status = 'success'
        '''
        with self.connect(read_only=True) as connection:
            return bool(connection.execute(query, [series_id, as_of_date]).fetchone()[0])

    def replace_historical_snapshot(
        self,
        series_id: str,
        as_of_date: date,
        frame: pd.DataFrame,
    ) -> int:
        downloaded_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
        marker = pd.DataFrame(
            [
                {
                    "series_id": series_id,
                    "as_of_date": as_of_date,
                    "row_count": int(len(frame)),
                    "downloaded_at": downloaded_at,
                    "status": "success",
                }
            ]
        )
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM historical_snapshots WHERE series_id = ? AND as_of_date = ?",
                [series_id, as_of_date],
            )
            if not frame.empty:
                connection.register("_snapshot", frame)
                connection.execute(
                    '''
                    INSERT INTO historical_snapshots
                    SELECT series_id, as_of_date, observation_date, value,
                           retrieved_at, source
                    FROM _snapshot
                    '''
                )
                connection.unregister("_snapshot")

            connection.execute(
                "DELETE FROM snapshot_downloads WHERE series_id = ? AND as_of_date = ?",
                [series_id, as_of_date],
            )
            connection.register("_marker", marker)
            connection.execute("INSERT INTO snapshot_downloads SELECT * FROM _marker")
            connection.unregister("_marker")
        return len(frame)

    def historical_snapshot(
        self,
        as_of_date: date,
        series_ids: list[str] | None = None,
    ) -> pd.DataFrame:
        where_clause = "WHERE as_of_date = ?"
        parameters: list = [as_of_date]
        if series_ids:
            placeholders = ", ".join(["?"] * len(series_ids))
            where_clause += f" AND series_id IN ({placeholders})"
            parameters.extend(series_ids)

        query = f'''
        SELECT series_id, observation_date, value, as_of_date AS realtime_start,
               as_of_date AS realtime_end, retrieved_at
        FROM historical_snapshots
        {where_clause}
        ORDER BY series_id, observation_date
        '''
        with self.connect(read_only=True) as connection:
            return connection.execute(query, parameters).fetchdf()

    def initial_release_date(
        self,
        series_id: str,
        target_period: pd.Period,
    ) -> date | None:
        start = target_period.start_time.date()
        end = target_period.end_time.date()
        query = '''
        SELECT MIN(realtime_start) AS release_date
        FROM observations
        WHERE series_id = ?
          AND vintage_type = 'initial'
          AND observation_date BETWEEN ? AND ?
        '''
        with self.connect(read_only=True) as connection:
            value = connection.execute(query, [series_id, start, end]).fetchone()[0]
        return value

    def query_df(self, query: str, parameters: list | None = None) -> pd.DataFrame:
        with self.connect(read_only=True) as connection:
            return connection.execute(query, parameters or []).fetchdf()

    def save_model_outputs(
        self,
        run_record: pd.DataFrame,
        forecasts: pd.DataFrame,
        coefficients: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            for table, frame in [
                ("model_runs", run_record),
                ("forecasts", forecasts),
                ("model_coefficients", coefficients),
            ]:
                connection.register(f"_{table}", frame)
                connection.execute(f"INSERT INTO {table} SELECT * FROM _{table}")
                connection.unregister(f"_{table}")


    def save_inflation_outputs(
        self,
        run_record: pd.DataFrame,
        forecasts: pd.DataFrame,
        coefficients: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            for table, frame in [
                ("inflation_model_runs", run_record),
                ("inflation_forecasts", forecasts),
                ("inflation_coefficients", coefficients),
            ]:
                if frame.empty:
                    continue
                connection.register(f"_{table}", frame)
                connection.execute(f"INSERT INTO {table} SELECT * FROM _{table}")
                connection.unregister(f"_{table}")

    def save_labour_outputs(
        self,
        run_record: pd.DataFrame,
        forecasts: pd.DataFrame,
        coefficients: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            for table, frame in [
                ("labour_model_runs", run_record),
                ("labour_forecasts", forecasts),
                ("labour_coefficients", coefficients),
            ]:
                if frame.empty:
                    continue
                connection.register(f"_{table}", frame)
                connection.execute(f"INSERT INTO {table} SELECT * FROM _{table}")
                connection.unregister(f"_{table}")

    def save_labour_backtest_outputs(
        self,
        run_record: pd.DataFrame,
        results: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_labour_backtest_run", run_record)
            connection.execute(
                "INSERT INTO labour_backtest_runs SELECT * FROM _labour_backtest_run"
            )
            connection.unregister("_labour_backtest_run")
            if not results.empty:
                connection.register("_labour_backtest_results", results)
                connection.execute(
                    "INSERT INTO labour_backtest_results SELECT * FROM _labour_backtest_results"
                )
                connection.unregister("_labour_backtest_results")

    def save_labour_vintage_backtest_outputs(
        self,
        run_record: pd.DataFrame,
        results: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_labour_vintage_run", run_record)
            connection.execute(
                "INSERT INTO labour_vintage_backtest_runs SELECT * FROM _labour_vintage_run"
            )
            connection.unregister("_labour_vintage_run")
            if not results.empty:
                connection.register("_labour_vintage_results", results)
                connection.execute(
                    "INSERT INTO labour_vintage_backtest_results SELECT * FROM _labour_vintage_results"
                )
                connection.unregister("_labour_vintage_results")

    def save_labour_interval_calibration_outputs(
        self,
        run_record: pd.DataFrame,
        results: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_labour_interval_calibration_run", run_record)
            connection.execute(
                "INSERT INTO labour_interval_calibration_runs "
                "SELECT * FROM _labour_interval_calibration_run"
            )
            connection.unregister("_labour_interval_calibration_run")
            if not results.empty:
                connection.register("_labour_interval_calibrated_results", results)
                connection.execute(
                    "INSERT INTO labour_interval_calibrated_results "
                    "SELECT * FROM _labour_interval_calibrated_results"
                )
                connection.unregister("_labour_interval_calibrated_results")

    def save_labour_validation_outputs(
        self,
        run_record: pd.DataFrame,
        checks: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_labour_validation_run", run_record)
            connection.execute(
                "INSERT INTO labour_validation_runs SELECT * FROM _labour_validation_run"
            )
            connection.unregister("_labour_validation_run")
            if not checks.empty:
                connection.register("_labour_validation_checks", checks)
                connection.execute(
                    "INSERT INTO labour_validation_checks SELECT * FROM _labour_validation_checks"
                )
                connection.unregister("_labour_validation_checks")

    def save_labour_live_outputs(
        self,
        run_record: pd.DataFrame,
        forecasts: pd.DataFrame,
        components: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_labour_live_run", run_record)
            connection.execute("INSERT INTO labour_live_runs SELECT * FROM _labour_live_run")
            connection.unregister("_labour_live_run")
            if not forecasts.empty:
                connection.register("_labour_live_forecasts", forecasts)
                connection.execute(
                    "INSERT INTO labour_live_forecasts SELECT * FROM _labour_live_forecasts"
                )
                connection.unregister("_labour_live_forecasts")
            if not components.empty:
                connection.register("_labour_live_components", components)
                connection.execute(
                    "INSERT INTO labour_live_components SELECT * FROM _labour_live_components"
                )
                connection.unregister("_labour_live_components")

    def save_labour_live_information_set(
        self,
        run_id: str,
        observations: pd.DataFrame,
    ) -> int:
        if observations.empty:
            return 0
        frame = observations.copy()
        frame["run_id"] = run_id
        if "retrieved_at" not in frame.columns:
            frame["retrieved_at"] = pd.Timestamp.now(tz="UTC").tz_localize(None)
        for column in ["realtime_start", "realtime_end"]:
            if column not in frame.columns:
                frame[column] = pd.NaT
        frame = frame[
            [
                "run_id", "series_id", "observation_date", "value",
                "realtime_start", "realtime_end", "retrieved_at",
            ]
        ]
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM labour_live_information_sets WHERE run_id = ?", [run_id]
            )
            connection.register("_labour_live_information_set", frame)
            connection.execute(
                "INSERT INTO labour_live_information_sets "
                "SELECT * FROM _labour_live_information_set"
            )
            connection.unregister("_labour_live_information_set")
        return int(len(frame))

    def labour_live_information_set(self, run_id: str) -> pd.DataFrame:
        return self.query_df(
            """
            SELECT series_id, observation_date, value, realtime_start, realtime_end,
                   retrieved_at
            FROM labour_live_information_sets
            WHERE run_id = ?
            ORDER BY series_id, observation_date
            """,
            [run_id],
        )

    def save_labour_news_outputs(
        self,
        runs: pd.DataFrame,
        contributions: pd.DataFrame,
        changes: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            if not runs.empty:
                current_ids = runs["current_run_id"].dropna().astype(str).unique().tolist()
                for current_id in current_ids:
                    existing = connection.execute(
                        "SELECT decomposition_id FROM labour_news_runs WHERE current_run_id = ?",
                        [current_id],
                    ).fetchall()
                    ids = [row[0] for row in existing]
                    if ids:
                        placeholders = ", ".join(["?"] * len(ids))
                        connection.execute(
                            f"DELETE FROM labour_news_contributions WHERE decomposition_id IN ({placeholders})",
                            ids,
                        )
                        connection.execute(
                            f"DELETE FROM labour_release_changes WHERE decomposition_id IN ({placeholders})",
                            ids,
                        )
                    connection.execute(
                        "DELETE FROM labour_news_runs WHERE current_run_id = ?", [current_id]
                    )
                connection.register("_labour_news_runs", runs)
                connection.execute("INSERT INTO labour_news_runs SELECT * FROM _labour_news_runs")
                connection.unregister("_labour_news_runs")
            if not contributions.empty:
                connection.register("_labour_news_contributions", contributions)
                connection.execute(
                    "INSERT INTO labour_news_contributions "
                    "SELECT * FROM _labour_news_contributions"
                )
                connection.unregister("_labour_news_contributions")
            if not changes.empty:
                connection.register("_labour_release_changes", changes)
                connection.execute(
                    "INSERT INTO labour_release_changes SELECT * FROM _labour_release_changes"
                )
                connection.unregister("_labour_release_changes")

    def record_labour_news_failure(self, current_run_id: str, error: str) -> None:
        forecasts = self.query_df(
            "SELECT target_series, target_period, stable_point_forecast "
            "FROM labour_live_forecasts WHERE run_id = ? ORDER BY target_series",
            [current_run_id],
        )
        timestamp = pd.Timestamp.now(tz="UTC").tz_localize(None)
        rows = []
        import json
        import uuid
        import numpy as np
        for row in forecasts.itertuples(index=False):
            rows.append(
                {
                    "decomposition_id": str(uuid.uuid4()),
                    "current_run_id": current_run_id,
                    "previous_run_id": None,
                    "target_series": str(row.target_series),
                    "target_period": str(row.target_period),
                    "status": "failed",
                    "previous_forecast": np.nan,
                    "current_forecast": float(row.stable_point_forecast),
                    "total_change": np.nan,
                    "new_data_impact": np.nan,
                    "revision_impact": np.nan,
                    "model_refit_impact": np.nan,
                    "policy_change_impact": np.nan,
                    "residual_interaction": np.nan,
                    "details_json": json.dumps({"error": error}, default=str),
                    "created_at": timestamp,
                }
            )
        if rows:
            self.save_labour_news_outputs(pd.DataFrame(rows), pd.DataFrame(), pd.DataFrame())

    def save_inflation_backtest_outputs(
        self,
        run_record: pd.DataFrame,
        results: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_inflation_backtest_run", run_record)
            connection.execute(
                "INSERT INTO inflation_backtest_runs SELECT * FROM _inflation_backtest_run"
            )
            connection.unregister("_inflation_backtest_run")
            if not results.empty:
                connection.register("_inflation_backtest_results", results)
                connection.execute(
                    "INSERT INTO inflation_backtest_results SELECT * FROM _inflation_backtest_results"
                )
                connection.unregister("_inflation_backtest_results")



    def save_inflation_vintage_backtest_outputs(
        self,
        run_record: pd.DataFrame,
        results: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_inflation_vintage_run", run_record)
            connection.execute(
                "INSERT INTO inflation_vintage_backtest_runs SELECT * FROM _inflation_vintage_run"
            )
            connection.unregister("_inflation_vintage_run")
            if not results.empty:
                connection.register("_inflation_vintage_results", results)
                connection.execute(
                    "INSERT INTO inflation_vintage_backtest_results "
                    "SELECT * FROM _inflation_vintage_results"
                )
                connection.unregister("_inflation_vintage_results")

    def save_inflation_interval_calibration_outputs(
        self,
        run_record: pd.DataFrame,
        results: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_inflation_interval_calibration_run", run_record)
            connection.execute(
                "INSERT INTO inflation_interval_calibration_runs "
                "SELECT * FROM _inflation_interval_calibration_run"
            )
            connection.unregister("_inflation_interval_calibration_run")
            if not results.empty:
                connection.register("_inflation_interval_calibrated_results", results)
                connection.execute(
                    "INSERT INTO inflation_interval_calibrated_results "
                    "SELECT * FROM _inflation_interval_calibrated_results"
                )
                connection.unregister("_inflation_interval_calibrated_results")

    def save_inflation_validation_outputs(
        self,
        run_record: pd.DataFrame,
        checks: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_inflation_validation_run", run_record)
            connection.execute(
                "INSERT INTO inflation_validation_runs SELECT * FROM _inflation_validation_run"
            )
            connection.unregister("_inflation_validation_run")
            if not checks.empty:
                connection.register("_inflation_validation_checks", checks)
                connection.execute(
                    "INSERT INTO inflation_validation_checks "
                    "SELECT * FROM _inflation_validation_checks"
                )
                connection.unregister("_inflation_validation_checks")

    def save_inflation_live_outputs(
        self,
        run_record: pd.DataFrame,
        forecasts: pd.DataFrame,
        components: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_inflation_live_run", run_record)
            connection.execute("INSERT INTO inflation_live_runs SELECT * FROM _inflation_live_run")
            connection.unregister("_inflation_live_run")
            if not forecasts.empty:
                connection.register("_inflation_live_forecasts", forecasts)
                connection.execute(
                    "INSERT INTO inflation_live_forecasts SELECT * FROM _inflation_live_forecasts"
                )
                connection.unregister("_inflation_live_forecasts")
            if not components.empty:
                connection.register("_inflation_live_components", components)
                connection.execute(
                    "INSERT INTO inflation_live_components SELECT * FROM _inflation_live_components"
                )
                connection.unregister("_inflation_live_components")

    def save_inflation_live_information_set(
        self,
        run_id: str,
        observations: pd.DataFrame,
    ) -> int:
        if observations.empty:
            return 0
        frame = observations.copy()
        frame["run_id"] = run_id
        if "retrieved_at" not in frame.columns:
            frame["retrieved_at"] = pd.Timestamp.now(tz="UTC").tz_localize(None)
        for column in ["realtime_start", "realtime_end"]:
            if column not in frame.columns:
                frame[column] = pd.NaT
        frame = frame[
            [
                "run_id", "series_id", "observation_date", "value",
                "realtime_start", "realtime_end", "retrieved_at",
            ]
        ]
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM inflation_live_information_sets WHERE run_id = ?", [run_id]
            )
            connection.register("_inflation_live_information_set", frame)
            connection.execute(
                "INSERT INTO inflation_live_information_sets "
                "SELECT * FROM _inflation_live_information_set"
            )
            connection.unregister("_inflation_live_information_set")
        return int(len(frame))

    def inflation_live_information_set(self, run_id: str) -> pd.DataFrame:
        return self.query_df(
            """
            SELECT series_id, observation_date, value, realtime_start, realtime_end,
                   retrieved_at
            FROM inflation_live_information_sets
            WHERE run_id = ?
            ORDER BY series_id, observation_date
            """,
            [run_id],
        )

    def save_inflation_news_outputs(
        self,
        runs: pd.DataFrame,
        contributions: pd.DataFrame,
        changes: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            if not runs.empty:
                current_ids = runs["current_run_id"].dropna().astype(str).unique().tolist()
                for current_id in current_ids:
                    existing = connection.execute(
                        "SELECT decomposition_id FROM inflation_news_runs WHERE current_run_id = ?",
                        [current_id],
                    ).fetchall()
                    ids = [row[0] for row in existing]
                    if ids:
                        placeholders = ", ".join(["?"] * len(ids))
                        connection.execute(
                            f"DELETE FROM inflation_news_contributions WHERE decomposition_id IN ({placeholders})",
                            ids,
                        )
                        connection.execute(
                            f"DELETE FROM inflation_release_changes WHERE decomposition_id IN ({placeholders})",
                            ids,
                        )
                    connection.execute(
                        "DELETE FROM inflation_news_runs WHERE current_run_id = ?", [current_id]
                    )
                connection.register("_inflation_news_runs", runs)
                connection.execute("INSERT INTO inflation_news_runs SELECT * FROM _inflation_news_runs")
                connection.unregister("_inflation_news_runs")
            if not contributions.empty:
                connection.register("_inflation_news_contributions", contributions)
                connection.execute(
                    "INSERT INTO inflation_news_contributions "
                    "SELECT * FROM _inflation_news_contributions"
                )
                connection.unregister("_inflation_news_contributions")
            if not changes.empty:
                connection.register("_inflation_release_changes", changes)
                connection.execute(
                    "INSERT INTO inflation_release_changes SELECT * FROM _inflation_release_changes"
                )
                connection.unregister("_inflation_release_changes")

    def record_inflation_news_failure(self, current_run_id: str, error: str) -> None:
        forecasts = self.query_df(
            "SELECT target_series, target_period, stable_point_forecast "
            "FROM inflation_live_forecasts WHERE run_id = ? ORDER BY target_series",
            [current_run_id],
        )
        timestamp = pd.Timestamp.now(tz="UTC").tz_localize(None)
        rows = []
        import json
        import uuid
        import numpy as np
        for row in forecasts.itertuples(index=False):
            rows.append(
                {
                    "decomposition_id": str(uuid.uuid4()),
                    "current_run_id": current_run_id,
                    "previous_run_id": None,
                    "target_series": str(row.target_series),
                    "target_period": str(row.target_period),
                    "status": "failed",
                    "previous_forecast": np.nan,
                    "current_forecast": float(row.stable_point_forecast),
                    "total_change": np.nan,
                    "new_data_impact": np.nan,
                    "revision_impact": np.nan,
                    "model_refit_impact": np.nan,
                    "policy_change_impact": np.nan,
                    "residual_interaction": np.nan,
                    "details_json": json.dumps({"error": error}, default=str),
                    "created_at": timestamp,
                }
            )
        if rows:
            self.save_inflation_news_outputs(pd.DataFrame(rows), pd.DataFrame(), pd.DataFrame())

    def save_backtest_outputs(
        self,
        run_record: pd.DataFrame,
        results: pd.DataFrame,
        diagnostics: pd.DataFrame | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.register("_backtest_runs", run_record)
            connection.execute("INSERT INTO backtest_runs SELECT * FROM _backtest_runs")
            connection.unregister("_backtest_runs")

            if not results.empty:
                connection.register("_backtest_results", results)
                connection.execute(
                    "INSERT INTO backtest_results SELECT * FROM _backtest_results"
                )
                connection.unregister("_backtest_results")

            if diagnostics is not None and not diagnostics.empty:
                connection.register("_backtest_diagnostics", diagnostics)
                connection.execute(
                    "INSERT INTO backtest_diagnostics "
                    "SELECT * FROM _backtest_diagnostics"
                )
                connection.unregister("_backtest_diagnostics")

    def save_information_set(self, run_id: str, observations: pd.DataFrame) -> int:
        if observations.empty:
            return 0
        frame = observations.copy()
        frame["run_id"] = run_id
        frame["retrieved_at"] = pd.Timestamp.now(tz="UTC").tz_localize(None)
        for column in ["realtime_start", "realtime_end"]:
            if column not in frame.columns:
                frame[column] = pd.NaT
        frame = frame[
            [
                "run_id",
                "series_id",
                "observation_date",
                "value",
                "realtime_start",
                "realtime_end",
                "retrieved_at",
            ]
        ]
        with self.connect() as connection:
            connection.execute("DELETE FROM nowcast_information_sets WHERE run_id = ?", [run_id])
            connection.register("_information_set", frame)
            connection.execute(
                "INSERT INTO nowcast_information_sets SELECT * FROM _information_set"
            )
            connection.unregister("_information_set")
        return len(frame)

    def load_information_set(self, run_id: str) -> pd.DataFrame:
        return self.query_df(
            """
            SELECT series_id, observation_date, value, realtime_start,
                   realtime_end, retrieved_at
            FROM nowcast_information_sets
            WHERE run_id = ?
            ORDER BY series_id, observation_date
            """,
            [run_id],
        )

    def latest_prior_model_run(
        self,
        target_period: str,
        before_timestamp: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        query = """
        SELECT *
        FROM model_runs
        WHERE status = 'success' AND target_period = ?
        """
        parameters: list = [target_period]
        if before_timestamp is not None:
            query += " AND run_timestamp < ?"
            parameters.append(before_timestamp)
        query += " ORDER BY run_timestamp DESC LIMIT 1"
        return self.query_df(query, parameters)

    def save_news_outputs(
        self,
        news_run: pd.DataFrame,
        contributions: pd.DataFrame,
        release_changes: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_news_run", news_run)
            connection.execute("INSERT INTO nowcast_news_runs SELECT * FROM _news_run")
            connection.unregister("_news_run")
            if not contributions.empty:
                connection.register("_news_contributions", contributions)
                connection.execute(
                    "INSERT INTO nowcast_news_contributions "
                    "SELECT * FROM _news_contributions"
                )
                connection.unregister("_news_contributions")
            if not release_changes.empty:
                connection.register("_release_changes", release_changes)
                connection.execute(
                    "INSERT INTO nowcast_release_changes SELECT * FROM _release_changes"
                )
                connection.unregister("_release_changes")

    def replace_release_calendar(self, series_id: str, frame: pd.DataFrame) -> int:
        with self.connect() as connection:
            connection.execute("DELETE FROM release_calendar WHERE series_id = ?", [series_id])
            if not frame.empty:
                connection.register("_release_calendar", frame)
                connection.execute("INSERT INTO release_calendar SELECT * FROM _release_calendar")
                connection.unregister("_release_calendar")
        return len(frame)

    def register_model_identity(self, identity: dict, notes: str | None = None) -> None:
        frame = pd.DataFrame([
            {
                "model_id": identity["model_id"],
                "model_version": identity["model_version"],
                "display_name": identity["display_name"],
                "lifecycle_status": identity["lifecycle_status"],
                "config_hash": identity["config_hash"],
                "code_hash": identity["code_hash"],
                "git_commit": identity.get("git_commit"),
                "registered_at": pd.Timestamp.now(tz="UTC").tz_localize(None),
                "notes": notes,
            }
        ])
        with self.connect() as connection:
            connection.execute(
                """DELETE FROM model_registry WHERE model_id = ? AND model_version = ? """
                """AND config_hash = ? AND code_hash = ?""",
                [identity["model_id"], identity["model_version"], identity["config_hash"], identity["code_hash"]],
            )
            connection.register("_model_registry", frame)
            connection.execute("INSERT INTO model_registry SELECT * FROM _model_registry")
            connection.unregister("_model_registry")

    def register_model_approval(self, approval: dict) -> None:
        frame = pd.DataFrame([approval])
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM model_approvals WHERE model_id = ? AND promoted_version = ?",
                [approval["model_id"], approval["promoted_version"]],
            )
            connection.register("_model_approval", frame)
            connection.execute("INSERT INTO model_approvals SELECT * FROM _model_approval")
            connection.unregister("_model_approval")

    def save_forecast_registry(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        with self.connect() as connection:
            connection.execute("DELETE FROM forecast_registry WHERE run_id = ?", [frame.iloc[0]["run_id"]])
            connection.register("_forecast_registry", frame)
            connection.execute("INSERT INTO forecast_registry SELECT * FROM _forecast_registry")
            connection.unregister("_forecast_registry")

    def save_stage_backtest_outputs(
        self,
        run_record: pd.DataFrame,
        results: pd.DataFrame,
        diagnostics: pd.DataFrame | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.register("_stage_runs", run_record)
            connection.execute("INSERT INTO stage_backtest_runs SELECT * FROM _stage_runs")
            connection.unregister("_stage_runs")
            if not results.empty:
                connection.register("_stage_results", results)
                connection.execute("INSERT INTO stage_backtest_results SELECT * FROM _stage_results")
                connection.unregister("_stage_results")
            if diagnostics is not None and not diagnostics.empty:
                connection.register("_stage_diagnostics", diagnostics)
                connection.execute("INSERT INTO stage_backtest_diagnostics SELECT * FROM _stage_diagnostics")
                connection.unregister("_stage_diagnostics")

    def save_validation_outputs(
        self,
        validation_run: pd.DataFrame,
        checks: pd.DataFrame,
    ) -> None:
        with self.connect() as connection:
            connection.register("_validation_run", validation_run)
            connection.execute("INSERT INTO validation_runs SELECT * FROM _validation_run")
            connection.unregister("_validation_run")
            if not checks.empty:
                connection.register("_validation_checks", checks)
                connection.execute("INSERT INTO validation_checks SELECT * FROM _validation_checks")
                connection.unregister("_validation_checks")

    def save_macro_state_outputs(
        self,
        run_record: pd.DataFrame,
        dimensions: pd.DataFrame,
        inputs: pd.DataFrame,
        regimes: pd.DataFrame,
    ) -> None:
        run_columns = [
            "run_id",
            "model_id",
            "model_version",
            "run_timestamp",
            "state_as_of",
            "status",
            "primary_regime",
            "overall_confidence",
            "gdp_run_id",
            "inflation_run_id",
            "labour_run_id",
            "oldest_source_cutoff",
            "newest_source_cutoff",
            "cutoff_spread_days",
            "config_hash",
            "code_hash",
            "git_commit",
            "source_bundle_hash",
            "state_hash",
            "metrics_json",
            "notes",
        ]
        dimension_columns = [
            "run_id",
            "dimension",
            "score",
            "lower_score",
            "upper_score",
            "label",
            "confidence",
            "previous_run_id",
            "previous_score",
            "delta_score",
            "details_json",
            "created_at",
        ]
        input_columns = [
            "run_id",
            "source_model_id",
            "source_model_version",
            "source_run_id",
            "source_target",
            "source_target_name",
            "target_period",
            "forecast_stage",
            "point_forecast",
            "lower_80",
            "upper_80",
            "information_cutoff",
            "data_as_of",
            "source_hash",
            "created_at",
        ]
        regime_columns = [
            "run_id",
            "regime_code",
            "regime_label",
            "is_primary",
            "rule_strength",
            "rationale",
            "created_at",
        ]
        with self.connect() as connection:
            connection.register(
                "_macro_state_run", run_record[run_columns]
            )
            connection.execute(
                "INSERT INTO macro_state_runs SELECT * FROM _macro_state_run"
            )
            connection.unregister("_macro_state_run")

            connection.register(
                "_macro_state_dimensions",
                dimensions[dimension_columns],
            )
            connection.execute(
                "INSERT INTO macro_state_dimensions "
                "SELECT * FROM _macro_state_dimensions"
            )
            connection.unregister("_macro_state_dimensions")

            connection.register(
                "_macro_state_inputs", inputs[input_columns]
            )
            connection.execute(
                "INSERT INTO macro_state_inputs "
                "SELECT * FROM _macro_state_inputs"
            )
            connection.unregister("_macro_state_inputs")

            connection.register(
                "_macro_state_regimes", regimes[regime_columns]
            )
            connection.execute(
                "INSERT INTO macro_state_regimes "
                "SELECT * FROM _macro_state_regimes"
            )
            connection.unregister("_macro_state_regimes")

    def save_macro_state_history(
        self,
        metadata: pd.DataFrame,
        states: pd.DataFrame,
        inputs: pd.DataFrame,
        durations: pd.DataFrame,
        transitions: pd.DataFrame,
    ) -> None:
        metadata_columns = [
            "reconstruction_id",
            "model_id",
            "model_version",
            "start_date",
            "end_date",
            "months_requested",
            "months_reconstructed",
            "no_look_ahead_pass",
            "config_hash",
            "code_hash",
            "git_commit",
            "created_at",
            "notes",
            "source_mode",
            "gdp_source_id",
            "inflation_source_id",
            "labour_source_id",
            "coverage_ratio",
            "longest_contiguous_months",
        ]
        state_columns = [
            "reconstruction_id",
            "state_date",
            "growth_score",
            "inflation_score",
            "labour_score",
            "growth_lower",
            "growth_upper",
            "inflation_lower",
            "inflation_upper",
            "labour_lower",
            "labour_upper",
            "growth_label",
            "inflation_label",
            "labour_label",
            "primary_regime",
            "primary_regime_label",
            "primary_regime_strength",
            "possible_regimes_json",
            "possible_regime_count",
            "source_cutoff_spread_days",
            "no_look_ahead_pass",
            "source_bundle_hash",
            "created_at",
        ]
        input_columns = [
            "reconstruction_id",
            "state_date",
            "source_model_id",
            "source_model_version",
            "source_run_id",
            "source_target",
            "source_target_name",
            "target_period",
            "forecast_stage",
            "point_forecast",
            "lower_80",
            "upper_80",
            "information_cutoff",
            "data_as_of",
            "source_hash",
            "created_at",
            "source_validation_id",
            "interval_source",
            "actual_release_date",
            "target_leakage",
            "max_observation_date",
            "model_name",
            "information_set_hash",
        ]
        duration_columns = [
            "reconstruction_id",
            "primary_regime",
            "primary_regime_label",
            "start_date",
            "end_date",
            "months",
            "created_at",
        ]
        transition_columns = [
            "reconstruction_id",
            "from_regime",
            "to_regime",
            "transition_probability",
            "created_at",
        ]

        with self.connect() as connection:
            connection.register("_m1d_hist_meta", metadata[metadata_columns])
            connection.execute(
                """
                INSERT INTO macro_state_history_runs (
                    reconstruction_id, model_id, model_version, start_date,
                    end_date, months_requested, months_reconstructed,
                    no_look_ahead_pass, config_hash, code_hash, git_commit,
                    created_at, notes, source_mode, gdp_source_id,
                    inflation_source_id, labour_source_id, coverage_ratio,
                    longest_contiguous_months
                )
                SELECT * FROM _m1d_hist_meta
                """
            )
            connection.unregister("_m1d_hist_meta")

            connection.register("_m1d_hist_states", states[state_columns])
            connection.execute(
                """
                INSERT INTO macro_state_history_states (
                    reconstruction_id, state_date, growth_score,
                    inflation_score, labour_score, growth_lower,
                    growth_upper, inflation_lower, inflation_upper,
                    labour_lower, labour_upper, growth_label,
                    inflation_label, labour_label, primary_regime,
                    primary_regime_label, primary_regime_strength,
                    possible_regimes_json, possible_regime_count,
                    source_cutoff_spread_days, no_look_ahead_pass,
                    source_bundle_hash, created_at
                )
                SELECT * FROM _m1d_hist_states
                """
            )
            connection.unregister("_m1d_hist_states")

            connection.register("_m1d_hist_inputs", inputs[input_columns])
            connection.execute(
                """
                INSERT INTO macro_state_history_inputs (
                    reconstruction_id, state_date, source_model_id,
                    source_model_version, source_run_id, source_target,
                    source_target_name, target_period, forecast_stage,
                    point_forecast, lower_80, upper_80,
                    information_cutoff, data_as_of, source_hash, created_at,
                    source_validation_id, interval_source,
                    actual_release_date, target_leakage,
                    max_observation_date, model_name, information_set_hash
                )
                SELECT * FROM _m1d_hist_inputs
                """
            )
            connection.unregister("_m1d_hist_inputs")

            if not durations.empty:
                connection.register(
                    "_m1d_hist_durations", durations[duration_columns]
                )
                connection.execute(
                    """
                    INSERT INTO macro_state_history_durations (
                        reconstruction_id, primary_regime,
                        primary_regime_label, start_date, end_date,
                        months, created_at
                    )
                    SELECT * FROM _m1d_hist_durations
                    """
                )
                connection.unregister("_m1d_hist_durations")

            if not transitions.empty:
                connection.register(
                    "_m1d_hist_transitions",
                    transitions[transition_columns],
                )
                connection.execute(
                    """
                    INSERT INTO macro_state_history_transitions (
                        reconstruction_id, from_regime, to_regime,
                        transition_probability, created_at
                    )
                    SELECT * FROM _m1d_hist_transitions
                    """
                )
                connection.unregister("_m1d_hist_transitions")

    def save_macro_state_tournament(
        self,
        run_record: pd.DataFrame,
        candidates: pd.DataFrame,
        metrics: pd.DataFrame,
        monthly: pd.DataFrame,
    ) -> None:
        run_columns = [
            "tournament_id",
            "model_id",
            "model_version",
            "reconstruction_id",
            "created_at",
            "status",
            "training_start",
            "training_end",
            "validation_start",
            "validation_end",
            "holdout_start",
            "holdout_end",
            "training_months",
            "validation_months",
            "holdout_months",
            "core_candidates",
            "uncertainty_candidates",
            "selected_candidate_id",
            "selected_core_candidate_id",
            "selected_validation_score",
            "selected_holdout_rank",
            "config_hash",
            "code_hash",
            "git_commit",
            "baseline_metrics_json",
            "metrics_json",
            "report_path",
            "notes",
        ]
        candidate_columns = [
            "tournament_id",
            "candidate_id",
            "candidate_type",
            "core_candidate_id",
            "normalization_id",
            "inflation_weights_id",
            "labour_weights_id",
            "threshold_id",
            "uncertainty_id",
            "selected",
            "validation_rank",
            "holdout_rank",
            "validation_score",
            "holdout_score",
            "config_json",
            "created_at",
        ]
        metric_columns = [
            "tournament_id",
            "candidate_id",
            "split",
            "months",
            "dimension_rmse",
            "dimension_mae",
            "exact_regime_accuracy",
            "family_accuracy",
            "sign_accuracy",
            "forecast_churn",
            "actual_churn",
            "churn_gap",
            "distribution_jsd",
            "forecast_regime_entropy",
            "actual_regime_entropy",
            "regime_collapse_penalty",
            "forecast_regime_count",
            "actual_regime_count",
            "brier_score",
            "log_loss",
            "coverage_80",
            "coverage_gap",
            "mean_top_probability",
            "mean_effective_regimes",
            "top1_accuracy",
            "core_score",
            "uncertainty_score",
            "final_score",
            "created_at",
        ]
        monthly_columns = [
            "tournament_id",
            "candidate_id",
            "core_candidate_id",
            "uncertainty_id",
            "state_date",
            "split",
            "forecast_growth",
            "forecast_inflation",
            "forecast_labour",
            "actual_growth",
            "actual_inflation",
            "actual_labour",
            "growth_lower",
            "growth_upper",
            "inflation_lower",
            "inflation_upper",
            "labour_lower",
            "labour_upper",
            "forecast_regime",
            "actual_regime",
            "top_regime",
            "top_probability",
            "actual_regime_probability",
            "brier_score",
            "log_loss",
            "coverage_80",
            "effective_regimes",
            "probabilities_json",
            "created_at",
        ]
        with self.connect() as connection:
            connection.register("_m1d_tournament_run", run_record[run_columns])
            connection.execute(
                "INSERT INTO macro_state_tournament_runs "
                "SELECT * FROM _m1d_tournament_run"
            )
            connection.unregister("_m1d_tournament_run")

            connection.register(
                "_m1d_tournament_candidates",
                candidates[candidate_columns],
            )
            connection.execute(
                "INSERT INTO macro_state_tournament_candidates "
                "SELECT * FROM _m1d_tournament_candidates"
            )
            connection.unregister("_m1d_tournament_candidates")

            connection.register(
                "_m1d_tournament_metrics", metrics[metric_columns]
            )
            connection.execute(
                "INSERT INTO macro_state_tournament_metrics "
                "SELECT * FROM _m1d_tournament_metrics"
            )
            connection.unregister("_m1d_tournament_metrics")

            connection.register(
                "_m1d_tournament_monthly", monthly[monthly_columns]
            )
            connection.execute(
                "INSERT INTO macro_state_tournament_monthly "
                "SELECT * FROM _m1d_tournament_monthly"
            )
            connection.unregister("_m1d_tournament_monthly")

    def save_macro_state_stability_tournament(
        self,
        run_record: pd.DataFrame,
        folds: pd.DataFrame,
        candidates: pd.DataFrame,
        fold_metrics: pd.DataFrame,
        audit_metrics: pd.DataFrame,
        subperiod_metrics: pd.DataFrame,
    ) -> None:
        run_columns = [
            "stability_id", "model_id", "model_version",
            "reconstruction_id", "source_tournament_id", "created_at",
            "status", "fold_count", "selection_start", "selection_end",
            "selection_months", "audit_start", "audit_end", "audit_months",
            "core_candidates", "final_candidates", "selected_candidate_id",
            "selected_core_candidate_id", "selected_uncertainty_id",
            "selected_stability_score", "selected_stability_rank",
            "selected_governance_pass", "selected_audit_rank", "config_hash",
            "code_hash", "git_commit", "warnings_json", "report_path", "notes",
        ]
        fold_columns = [
            "stability_id", "fold_id", "training_start", "training_end",
            "training_months", "evaluation_start", "evaluation_end",
            "evaluation_months", "created_at",
        ]
        candidate_columns = [
            "stability_id", "candidate_id", "candidate_type",
            "core_candidate_id", "uncertainty_id", "selected",
            "governance_pass", "stability_rank", "stability_score", "folds",
            "mean_fold_score", "median_fold_score", "mean_fold_rank",
            "median_fold_rank", "rank_std", "best_fold_rank",
            "worst_fold_rank", "fold_win_rate", "leading_third_rate",
            "catastrophic_fold_count", "baseline_dominance_rate",
            "mean_baseline_margin", "average_regret",
            "regime_collapse_fold_rate", "uncertainty_method_win_rate",
            "proper_score_dominance_rate", "bootstrap_margin_mean",
            "bootstrap_margin_lower", "bootstrap_margin_upper",
            "audit_final_score", "audit_final_rank",
            "audit_exact_regime_accuracy", "audit_brier_score",
            "audit_log_loss", "audit_coverage_80", "audit_top1_accuracy",
            "audit_baseline_margin", "metrics_json", "created_at",
        ]
        metric_columns = [
            "stability_id", "fold_id", "candidate_id", "candidate_type",
            "core_candidate_id", "uncertainty_id", "evaluation_start",
            "evaluation_end", "evaluation_months", "score", "rank",
            "core_score", "uncertainty_score", "dimension_rmse",
            "exact_regime_accuracy", "family_accuracy", "sign_accuracy",
            "regime_collapse_penalty", "brier_score", "log_loss",
            "coverage_80", "top1_accuracy", "mode_accuracy",
            "persistence_accuracy", "strongest_baseline",
            "strongest_baseline_accuracy", "baseline_margin",
            "beats_strongest_baseline", "uncertainty_method_rank",
            "proper_score_improvement", "proper_score_dominates", "created_at",
        ]
        audit_columns = [
            "stability_id", "candidate_id", "core_candidate_id",
            "uncertainty_id", "audit_final_score", "audit_final_rank",
            "audit_core_score", "audit_core_rank", "audit_uncertainty_score",
            "audit_uncertainty_rank", "audit_exact_regime_accuracy",
            "audit_family_accuracy", "audit_sign_accuracy",
            "audit_dimension_rmse", "audit_regime_collapse_penalty",
            "audit_brier_score", "audit_log_loss", "audit_coverage_80",
            "audit_top1_accuracy", "audit_mean_effective_regimes",
            "audit_baseline_accuracy", "audit_baseline_margin", "created_at",
        ]
        subperiod_columns = [
            "stability_id", "candidate_id", "subperiod_id", "start_date",
            "end_date", "months", "dimension_rmse",
            "exact_regime_accuracy", "family_accuracy", "sign_accuracy",
            "regime_collapse_penalty", "brier_score", "log_loss",
            "coverage_80", "top1_accuracy", "mean_effective_regimes",
            "created_at",
        ]
        with self.connect() as connection:
            for name, table, frame, columns in [
                ("_m1d_stability_run", "macro_state_stability_runs", run_record, run_columns),
                ("_m1d_stability_folds", "macro_state_stability_folds", folds, fold_columns),
                ("_m1d_stability_candidates", "macro_state_stability_candidates", candidates, candidate_columns),
                ("_m1d_stability_fold_metrics", "macro_state_stability_fold_metrics", fold_metrics, metric_columns),
                ("_m1d_stability_audit", "macro_state_stability_audit_metrics", audit_metrics, audit_columns),
                ("_m1d_stability_subperiod", "macro_state_stability_subperiod_metrics", subperiod_metrics, subperiod_columns),
            ]:
                if frame.empty:
                    continue
                connection.register(name, frame[columns])
                connection.execute(f"INSERT INTO {table} SELECT * FROM {name}")
                connection.unregister(name)

    @staticmethod
    def _require_shadow_columns(
        frame: pd.DataFrame,
        required: list[str],
        frame_name: str,
    ) -> None:
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(
                f"{frame_name} is missing required columns: {missing}"
            )

    @staticmethod
    def _shadow_timestamp(value: object, field_name: str) -> pd.Timestamp:
        try:
            timestamp = pd.Timestamp(value)
        except Exception as exc:
            raise ValueError(
                f"{field_name} is not a valid timestamp: {value!r}"
            ) from exc
        if pd.isna(timestamp):
            raise ValueError(f"{field_name} must not be null")
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert("UTC").tz_localize(None)
        return timestamp

    @staticmethod
    def _shadow_true(series: pd.Series, field_name: str) -> None:
        if series.isna().any() or not series.map(bool).all():
            raise ValueError(f"{field_name} must be true for every row")

    @staticmethod
    def _shadow_match(
        frame: pd.DataFrame,
        column: str,
        expected: object,
        frame_name: str,
    ) -> None:
        if column in {"state_date", "information_cutoff"}:
            expected_value = pd.Timestamp(expected).normalize()
            observed = (
                pd.to_datetime(frame[column], errors="coerce")
                .map(lambda value: value.normalize() if not pd.isna(value) else value)
                .drop_duplicates()
                .tolist()
            )
        else:
            expected_value = expected
            observed = frame[column].drop_duplicates().tolist()
        if len(observed) != 1 or observed[0] != expected_value:
            raise ValueError(
                f"{frame_name}.{column} must equal {expected_value!r}; "
                f"observed {observed!r}"
            )

    def save_macro_state_shadow_predictions(
        self,
        run_record: pd.DataFrame,
        predictions: pd.DataFrame,
        dimensions: pd.DataFrame,
    ) -> None:
        run_columns = [
            "shadow_run_id", "model_id", "model_version", "run_timestamp",
            "state_date", "information_cutoff", "target_mode",
            "target_horizon_days", "target_expected_available_date",
            "source_candidate_id", "source_evidence_version",
            "primary_comparator", "source_macro_state_run_id", "gdp_run_id",
            "inflation_run_id", "labour_run_id", "config_hash", "code_hash",
            "git_commit", "information_set_hash", "source_bundle_hash",
            "no_look_ahead_pass", "status", "governance_json", "notes",
            "created_at",
        ]
        prediction_columns = [
            "shadow_run_id", "model_version", "state_date",
            "information_cutoff", "prediction_timestamp", "benchmark_id",
            "predicted_family", "predicted_probabilities_json",
            "top1_family", "top2_family", "top3_family", "top1_probability",
            "top2_probability", "top3_probability", "top1_top2_gap",
            "entropy", "probability_sum", "probability_vector_hash",
            "no_look_ahead_pass", "created_at",
        ]
        dimension_columns = [
            "shadow_run_id", "model_version", "state_date",
            "information_cutoff", "dimension", "score", "lower_score",
            "upper_score", "label", "confidence", "source_model_id",
            "source_model_version", "source_run_id",
            "source_information_cutoff", "source_data_as_of", "source_hash",
            "no_look_ahead_pass", "created_at",
        ]

        self._require_shadow_columns(run_record, run_columns, "run_record")
        self._require_shadow_columns(
            predictions, prediction_columns, "predictions"
        )
        self._require_shadow_columns(
            dimensions, dimension_columns, "dimensions"
        )

        if len(run_record) != 1:
            raise ValueError("run_record must contain exactly one row")
        if len(predictions) != 2:
            raise ValueError("predictions must contain exactly two rows")
        if len(dimensions) != 3:
            raise ValueError("dimensions must contain exactly three rows")

        expected_benchmarks = {"source", "rolling_frequency"}
        observed_benchmarks = set(
            predictions["benchmark_id"].dropna().astype(str)
        )
        if observed_benchmarks != expected_benchmarks:
            raise ValueError(
                "predictions must contain exactly the source and "
                "rolling_frequency benchmarks"
            )
        if predictions["benchmark_id"].duplicated().any():
            raise ValueError("prediction benchmark IDs must be unique")

        expected_dimensions = {"growth", "inflation", "labour"}
        observed_dimensions = set(
            dimensions["dimension"].dropna().astype(str)
        )
        if observed_dimensions != expected_dimensions:
            raise ValueError(
                "dimensions must contain exactly growth, inflation, and labour"
            )
        if dimensions["dimension"].duplicated().any():
            raise ValueError("dimension names must be unique")

        run = run_record.iloc[0]
        shadow_run_id = str(run["shadow_run_id"])
        model_version = str(run["model_version"])
        state_date = run["state_date"]
        information_cutoff = run["information_cutoff"]

        if not shadow_run_id:
            raise ValueError("shadow_run_id must not be empty")

        for frame, name in (
            (predictions, "predictions"),
            (dimensions, "dimensions"),
        ):
            self._shadow_match(
                frame, "shadow_run_id", shadow_run_id, name
            )
            self._shadow_match(
                frame, "model_version", model_version, name
            )
            self._shadow_match(frame, "state_date", state_date, name)
            self._shadow_match(
                frame, "information_cutoff", information_cutoff, name
            )

        self._shadow_true(
            run_record["no_look_ahead_pass"],
            "run_record.no_look_ahead_pass",
        )
        self._shadow_true(
            predictions["no_look_ahead_pass"],
            "predictions.no_look_ahead_pass",
        )
        self._shadow_true(
            dimensions["no_look_ahead_pass"],
            "dimensions.no_look_ahead_pass",
        )

        cutoff_timestamp = self._shadow_timestamp(
            information_cutoff, "information_cutoff"
        ).normalize()
        run_timestamp = self._shadow_timestamp(
            run["run_timestamp"], "run_timestamp"
        )
        target_expected = self._shadow_timestamp(
            run["target_expected_available_date"],
            "target_expected_available_date",
        ).normalize()

        if run_timestamp < cutoff_timestamp:
            raise ValueError(
                "run_timestamp must not precede information_cutoff"
            )
        if target_expected <= run_timestamp:
            raise ValueError(
                "target_expected_available_date must be later than "
                "run_timestamp"
            )

        for value in predictions["prediction_timestamp"]:
            prediction_timestamp = self._shadow_timestamp(
                value, "prediction_timestamp"
            )
            if prediction_timestamp < cutoff_timestamp:
                raise ValueError(
                    "prediction_timestamp must not precede "
                    "information_cutoff"
                )
            if prediction_timestamp >= target_expected:
                raise ValueError(
                    "prediction_timestamp must precede expected target "
                    "availability"
                )

        source_cutoffs = dimensions["source_information_cutoff"].map(
            lambda value: self._shadow_timestamp(
                value, "source_information_cutoff"
            ).normalize()
        )
        if (source_cutoffs > cutoff_timestamp).any():
            raise ValueError(
                "dimension source information cutoffs must not exceed the "
                "shadow information cutoff"
            )

        probability_sums = pd.to_numeric(
            predictions["probability_sum"], errors="coerce"
        )
        if probability_sums.isna().any():
            raise ValueError("probability_sum must be finite")
        if ((probability_sums - 1.0).abs() > 1.0e-10).any():
            raise ValueError(
                "probability_sum must equal 1.0 within tolerance 1e-10"
            )

        run_frame = run_record[run_columns].copy()
        prediction_frame = predictions[prediction_columns].copy()
        dimension_frame = dimensions[dimension_columns].copy()

        with self.connect() as connection:
            connection.execute("BEGIN TRANSACTION")
            try:
                duplicate_run = connection.execute(
                    """
                    SELECT shadow_run_id
                    FROM macro_state_shadow_runs
                    WHERE shadow_run_id = ?
                       OR (model_version = ? AND state_date = ?)
                    LIMIT 1
                    """,
                    [shadow_run_id, model_version, state_date],
                ).fetchone()
                if duplicate_run is not None:
                    raise ValueError(
                        "append-only violation: a shadow run already exists "
                        "for this run ID or model-version/state-date"
                    )

                for benchmark_id in sorted(expected_benchmarks):
                    duplicate_prediction = connection.execute(
                        """
                        SELECT shadow_run_id
                        FROM macro_state_shadow_predictions
                        WHERE (
                            shadow_run_id = ? AND benchmark_id = ?
                        ) OR (
                            model_version = ?
                            AND state_date = ?
                            AND benchmark_id = ?
                        )
                        LIMIT 1
                        """,
                        [
                            shadow_run_id, benchmark_id, model_version,
                            state_date, benchmark_id,
                        ],
                    ).fetchone()
                    if duplicate_prediction is not None:
                        raise ValueError(
                            "append-only violation: a shadow prediction "
                            f"already exists for benchmark {benchmark_id}"
                        )

                connection.register("_m1d_shadow_run", run_frame)
                connection.execute(
                    """
                    INSERT INTO macro_state_shadow_runs (
                        shadow_run_id, model_id, model_version, run_timestamp,
                        state_date, information_cutoff, target_mode,
                        target_horizon_days, target_expected_available_date,
                        source_candidate_id, source_evidence_version,
                        primary_comparator, source_macro_state_run_id,
                        gdp_run_id, inflation_run_id, labour_run_id,
                        config_hash, code_hash, git_commit,
                        information_set_hash, source_bundle_hash,
                        no_look_ahead_pass, status, governance_json, notes,
                        created_at
                    )
                    SELECT * FROM _m1d_shadow_run
                    """
                )
                connection.unregister("_m1d_shadow_run")

                connection.register(
                    "_m1d_shadow_predictions", prediction_frame
                )
                connection.execute(
                    """
                    INSERT INTO macro_state_shadow_predictions (
                        shadow_run_id, model_version, state_date,
                        information_cutoff, prediction_timestamp,
                        benchmark_id, predicted_family,
                        predicted_probabilities_json, top1_family,
                        top2_family, top3_family, top1_probability,
                        top2_probability, top3_probability, top1_top2_gap,
                        entropy, probability_sum, probability_vector_hash,
                        no_look_ahead_pass, created_at
                    )
                    SELECT * FROM _m1d_shadow_predictions
                    """
                )
                connection.unregister("_m1d_shadow_predictions")

                connection.register(
                    "_m1d_shadow_dimensions", dimension_frame
                )
                connection.execute(
                    """
                    INSERT INTO macro_state_shadow_dimensions (
                        shadow_run_id, model_version, state_date,
                        information_cutoff, dimension, score, lower_score,
                        upper_score, label, confidence, source_model_id,
                        source_model_version, source_run_id,
                        source_information_cutoff, source_data_as_of,
                        source_hash, no_look_ahead_pass, created_at
                    )
                    SELECT * FROM _m1d_shadow_dimensions
                    """
                )
                connection.unregister("_m1d_shadow_dimensions")
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def save_macro_state_shadow_outcomes(
        self,
        outcomes: pd.DataFrame,
    ) -> None:
        outcome_columns = [
            "outcome_id", "shadow_run_id", "model_version", "state_date",
            "benchmark_id", "resolved_at", "target_mode",
            "target_horizon_days", "target_available_date",
            "target_vintage_id", "actual_family",
            "actual_probabilities_json", "actual_confidence",
            "actual_probability", "brier_score", "log_loss", "top1_hit",
            "top2_hit", "top3_hit", "previous_actual_family",
            "transition_flag", "target_hash", "evaluation_hash",
            "no_look_ahead_pass", "created_at",
        ]
        self._require_shadow_columns(outcomes, outcome_columns, "outcomes")

        if len(outcomes) != 2:
            raise ValueError("outcomes must contain exactly two rows")
        expected_benchmarks = {"source", "rolling_frequency"}
        observed_benchmarks = set(
            outcomes["benchmark_id"].dropna().astype(str)
        )
        if observed_benchmarks != expected_benchmarks:
            raise ValueError(
                "outcomes must contain exactly the source and "
                "rolling_frequency benchmarks"
            )
        if outcomes["benchmark_id"].duplicated().any():
            raise ValueError("outcome benchmark IDs must be unique")
        if outcomes["outcome_id"].isna().any():
            raise ValueError("outcome_id must not be null")
        if outcomes["outcome_id"].astype(str).duplicated().any():
            raise ValueError("outcome IDs must be unique")

        invariant_columns = [
            "shadow_run_id", "model_version", "state_date", "target_mode",
            "target_horizon_days", "target_available_date",
            "target_vintage_id", "actual_family",
            "actual_probabilities_json", "actual_confidence",
            "previous_actual_family", "transition_flag", "target_hash",
        ]
        for column in invariant_columns:
            if outcomes[column].nunique(dropna=False) != 1:
                raise ValueError(
                    f"outcomes.{column} must be identical across benchmarks"
                )

        self._shadow_true(
            outcomes["no_look_ahead_pass"],
            "outcomes.no_look_ahead_pass",
        )

        actual_probabilities = pd.to_numeric(
            outcomes["actual_probability"], errors="coerce"
        )
        if actual_probabilities.isna().any() or (
            (actual_probabilities < 0.0) | (actual_probabilities > 1.0)
        ).any():
            raise ValueError("actual_probability must be between 0 and 1")

        for metric in ("brier_score", "log_loss"):
            values = pd.to_numeric(outcomes[metric], errors="coerce")
            if values.isna().any() or (values < 0.0).any():
                raise ValueError(f"{metric} must be finite and non-negative")

        for row in outcomes.itertuples(index=False):
            resolved_at = self._shadow_timestamp(
                row.resolved_at, "resolved_at"
            )
            target_available = self._shadow_timestamp(
                row.target_available_date, "target_available_date"
            ).normalize()
            if resolved_at < target_available:
                raise ValueError(
                    "resolved_at must not precede target_available_date"
                )

        first = outcomes.iloc[0]
        previous_family = first["previous_actual_family"]
        expected_transition = (
            False
            if pd.isna(previous_family) or previous_family is None
            else str(first["actual_family"]) != str(previous_family)
        )
        if bool(first["transition_flag"]) != expected_transition:
            raise ValueError(
                "transition_flag must equal actual_family != "
                "previous_actual_family"
            )

        shadow_run_id = str(first["shadow_run_id"])
        model_version = str(first["model_version"])
        state_date = first["state_date"]
        outcome_frame = outcomes[outcome_columns].copy()

        with self.connect() as connection:
            connection.execute("BEGIN TRANSACTION")
            try:
                run = connection.execute(
                    """
                    SELECT model_version, state_date, target_mode,
                           target_horizon_days
                    FROM macro_state_shadow_runs
                    WHERE shadow_run_id = ?
                    """,
                    [shadow_run_id],
                ).fetchone()
                if run is None:
                    raise ValueError(
                        "cannot resolve outcomes before the shadow run exists"
                    )
                if (
                    str(run[0]) != model_version
                    or pd.Timestamp(run[1]).normalize()
                    != pd.Timestamp(state_date).normalize()
                    or str(run[2]) != str(first["target_mode"])
                    or int(run[3]) != int(first["target_horizon_days"])
                ):
                    raise ValueError(
                        "outcome lineage does not match the persisted "
                        "shadow run"
                    )

                predictions = connection.execute(
                    """
                    SELECT benchmark_id
                    FROM macro_state_shadow_predictions
                    WHERE shadow_run_id = ?
                    """,
                    [shadow_run_id],
                ).fetchall()
                prediction_benchmarks = {str(row[0]) for row in predictions}
                if prediction_benchmarks != expected_benchmarks:
                    raise ValueError(
                        "both persisted benchmark predictions must exist "
                        "before outcome resolution"
                    )

                duplicate_outcome = connection.execute(
                    """
                    SELECT outcome_id
                    FROM macro_state_shadow_outcomes
                    WHERE shadow_run_id = ?
                       OR outcome_id IN (?, ?)
                    LIMIT 1
                    """,
                    [
                        shadow_run_id,
                        str(outcomes.iloc[0]["outcome_id"]),
                        str(outcomes.iloc[1]["outcome_id"]),
                    ],
                ).fetchone()
                if duplicate_outcome is not None:
                    raise ValueError(
                        "append-only violation: outcomes already exist for "
                        "this shadow run or outcome ID"
                    )

                connection.register("_m1d_shadow_outcomes", outcome_frame)
                connection.execute(
                    """
                    INSERT INTO macro_state_shadow_outcomes (
                        outcome_id, shadow_run_id, model_version, state_date,
                        benchmark_id, resolved_at, target_mode,
                        target_horizon_days, target_available_date,
                        target_vintage_id, actual_family,
                        actual_probabilities_json, actual_confidence,
                        actual_probability, brier_score, log_loss, top1_hit,
                        top2_hit, top3_hit, previous_actual_family,
                        transition_flag, target_hash, evaluation_hash,
                        no_look_ahead_pass, created_at
                    )
                    SELECT * FROM _m1d_shadow_outcomes
                    """
                )
                connection.unregister("_m1d_shadow_outcomes")
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

