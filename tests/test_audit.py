import json

import pandas as pd

from macropulse.governance.audit import audit_stage_backtest


def _valid_results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "forecast_stage": "quarter_end",
                "forecast_date": "2023-03-31",
                "target_period": "2023Q1",
                "actual_release_date": "2023-04-27",
                "model_name": "Bridge Ridge",
                "point_forecast": 2.0,
                "actual": 1.8,
                "information_set_hash": "a" * 64,
                "interval_details_json": json.dumps(
                    {"max_prior_forecast_date": "2022-12-31"}
                ),
            }
        ]
    )


def test_valid_backtest_passes_core_audit() -> None:
    diagnostics = pd.DataFrame(
        [
            {
                "model_name": "Rolling Bridge–DFM Ensemble",
                "forecast_date": "2023-03-31",
                "details_json": json.dumps(
                    {"max_prior_forecast_date": "2022-12-31"}
                ),
            }
        ]
    )
    checks = audit_stage_backtest(_valid_results(), diagnostics, 0)
    assert all(check.status == "pass" for check in checks)


def test_future_weight_history_is_detected() -> None:
    diagnostics = pd.DataFrame(
        [
            {
                "model_name": "Rolling Bridge–DFM Ensemble",
                "forecast_date": "2023-03-31",
                "details_json": json.dumps(
                    {"max_prior_forecast_date": "2023-06-30"}
                ),
            }
        ]
    )
    checks = audit_stage_backtest(_valid_results(), diagnostics, 0)
    weight_check = next(
        check
        for check in checks
        if check.check_name == "Rolling ensemble weights use prior quarters only"
    )
    assert weight_check.status == "fail"
