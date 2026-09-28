from datetime import date
import numpy as np
import pandas as pd
import pytest

from macropulse.slack.production import (
    DENSE_MODEL2_HORIZONS, GOVERNED_REPORT_HORIZONS,
    extract_model2_gdp_growth_draws_by_name,
    forward_gap_provenance_dimensions,
)


def test_model2_gdp_draw_extraction_is_by_name_not_position():
    draws=np.zeros((3,8,4),dtype=float)
    draws[:,:,2]=7.5
    names=("policy_rate","unemployment_rate","real_gdp_growth","core_pce_inflation")
    got=extract_model2_gdp_growth_draws_by_name(draws,names)
    assert got.shape==(3,8)
    assert np.all(got==7.5)


def test_model2_gdp_draw_extraction_fails_without_unique_name():
    draws=np.zeros((2,8,4))
    with pytest.raises(ValueError):
        extract_model2_gdp_growth_draws_by_name(draws,("a","b","c","d"))


def test_dense_and_report_horizon_provenance_are_distinct():
    p=forward_gap_provenance_dimensions()
    assert tuple(p["dense_path_horizons"])==tuple(range(1,9))
    assert tuple(p["governed_report_horizons"])==(1,2,4,8)
    assert tuple(p["dense_path_horizons"]) != tuple(p["governed_report_horizons"])
