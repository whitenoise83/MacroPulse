import numpy as np
import pytest
from macropulse.slack.forward_gap import (
    GOVERNED_HORIZONS, ESTIMATE_CLASS, Model2GDPDrawProvenance,
    compound_dense_real_gdp_levels, compound_real_gdp_levels,
    deterministic_potential_log_path, forward_gap_distribution,
)

def prov(origin="2024Q4"):
    return Model2GDPDrawProvenance(
        model2_origin_quarter=origin,
        model2_candidate_id="bvar::p2-lambda0.2",
        model2_draw_hash="drawhash",
        model2_estimation_panel_hash="panelhash",
        model2_seed=123,
    )

def test_governed_horizons():
    assert GOVERNED_HORIZONS==(1,2,4,8)

def test_sparse_report_draws_fail_closed_for_level_compounding():
    with pytest.raises(ValueError,match="Sparse governed report-horizon"):
        compound_real_gdp_levels(np.ones((100,4)),origin_real_gdp_level=100.0)

def test_dense_growth_compounds_to_report_levels():
    x=np.full((2,8),4.0)
    got=compound_dense_real_gdp_levels(x,origin_real_gdp_level=100.0)
    expected=100*np.exp(np.array([1,2,4,8])/100.0)
    np.testing.assert_allclose(got[0],expected)

def test_potential_path_uses_model3_origin_state():
    got=deterministic_potential_log_path(
        origin_potential_log=np.log(100.0),origin_quarterly_trend_growth=.005)
    np.testing.assert_allclose(got,np.log(100.0)+np.array([1,2,4,8])*.005)

def test_equal_gdp_and_potential_paths_make_zero_gap():
    growth=np.full((200,8),2.0) # annualised log growth => .005 quarterly
    result=forward_gap_distribution(
        dense_gdp_growth_draws_annualized_pct=growth,
        origin_real_gdp_level=100.0,
        origin_potential_log=np.log(100.0),
        origin_quarterly_trend_growth=.005,
        origin_quarter="2024Q4",provenance=prov())
    np.testing.assert_allclose(result.gap_draws_pct,0.0,atol=1e-10)
    assert result.target_quarters==("2025Q1","2025Q2","2025Q4","2026Q4")
    assert set(result.summary["estimate_class"])=={ESTIMATE_CLASS}

def test_distribution_preserves_draw_count_and_uncertainty():
    rng=np.random.default_rng(7)
    growth=rng.normal(2.0,1.0,size=(500,8))
    result=forward_gap_distribution(
        dense_gdp_growth_draws_annualized_pct=growth,
        origin_real_gdp_level=100.0,
        origin_potential_log=np.log(100.0),
        origin_quarterly_trend_growth=.005,
        origin_quarter="2024Q4",provenance=prov())
    assert result.gap_draws_pct.shape==(500,4)
    assert (result.summary["upper_80"]>result.summary["lower_80"]).all()
    assert (result.summary["n_draws"]==500).all()

def test_origin_mismatch_fails_closed():
    with pytest.raises(ValueError,match="origins do not match"):
        forward_gap_distribution(
            dense_gdp_growth_draws_annualized_pct=np.ones((10,8)),
            origin_real_gdp_level=100.0,
            origin_potential_log=np.log(100.0),
            origin_quarterly_trend_growth=.005,
            origin_quarter="2024Q3",provenance=prov("2024Q4"))

def test_nonfinite_draws_fail():
    x=np.ones((10,8)); x[0,3]=np.nan
    with pytest.raises(ValueError,match="finite"):
        compound_dense_real_gdp_levels(x,origin_real_gdp_level=100.0)


def test_dense_model2_adapter_calls_frozen_simulator(monkeypatch):
    import macropulse.bvar.probabilistic as prob
    import macropulse.slack.forward_gap as fg
    assert fg.DENSE_PATH_HORIZONS == tuple(range(1, 9))
    class Result:
        horizons = tuple(range(1, 9))
        draws = np.ones((25, 8, 4))
        draw_hash = "dense-hash"
    seen = {}
    def fake(panel, posterior, *, n_simulations, seed, horizons):
        seen.update(n=n_simulations, seed=seed, horizons=horizons)
        return Result()
    monkeypatch.setattr(prob, "simulate_posterior_predictive", fake)
    out = fg.simulate_dense_model2_predictive(object(), object(), n_simulations=25, seed=77)
    assert seen == {"n":25, "seed":77, "horizons":tuple(range(1,9))}
    assert out.draw_hash == "dense-hash"

def test_dense_model2_adapter_rejects_sparse_return(monkeypatch):
    import macropulse.bvar.probabilistic as prob
    import macropulse.slack.forward_gap as fg
    class Result:
        horizons = (1,2,4,8)
        draws = np.ones((25,4,4))
        draw_hash = "sparse"
    monkeypatch.setattr(prob, "simulate_posterior_predictive", lambda *a, **k: Result())
    with pytest.raises(ValueError, match="dense 1..8"):
        fg.simulate_dense_model2_predictive(object(), object(), n_simulations=25, seed=77)
