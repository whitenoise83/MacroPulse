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

