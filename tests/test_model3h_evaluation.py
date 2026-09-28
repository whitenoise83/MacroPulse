import numpy as np
import pandas as pd
import pytest
from macropulse.slack.evaluation import (
    ESTIMATE_LABEL, EndpointResult, PseudoRealTimeOrigin,
    coverage_summary, endpoint_changes, revision_errors,
    validate_endpoint, validate_origins,
)

def origin(q,i):
    return PseudoRealTimeOrigin(f"id{i}",q,f"{q[:4]}-12-31",f"hash{i}")

def test_origin_grid_requires_order_and_identity():
    out=validate_origins([origin("2020Q1",1),origin("2020Q2",2)])
    assert len(out)==2
    with pytest.raises(ValueError):
        validate_origins([origin("2020Q2",1),origin("2020Q1",2)])

def test_duplicate_quarter_rejected():
    with pytest.raises(ValueError):
        validate_origins([origin("2020Q1",1),origin("2020Q1",2)])

def test_endpoint_label_and_candidate_governed():
    r=EndpointResult(origin("2020Q1",1),"3D",-2.0,True,True,{})
    assert validate_endpoint(r).estimate_label==ESTIMATE_LABEL
    with pytest.raises(ValueError):
        validate_endpoint(EndpointResult(origin("2020Q1",1),"X",0,True,True,{}))

def test_endpoint_changes_are_candidate_specific():
    x=pd.DataFrame({
      "candidate_id":["3D","3D","3E_A","3E_A"],
      "origin_quarter":["2020Q1","2020Q2","2020Q1","2020Q2"],
      "endpoint_gap_pct":[-2,-1,-3,-1],
    })
    y=endpoint_changes(x)
    assert np.isnan(y.loc[y.candidate_id=="3D","endpoint_change_pp"].iloc[0])
    assert y.loc[y.candidate_id=="3D","endpoint_change_pp"].iloc[1]==1
    assert y.loc[y.candidate_id=="3E_A","endpoint_change_pp"].iloc[1]==2

def test_revision_metrics():
    x=revision_errors(np.array([-2.,0.,1.]),np.array([-1.,0.,2.]))
    assert x["mean_revision_pp"]==pytest.approx(2/3)
    assert x["mae_revision_pp"]==pytest.approx(2/3)
    assert x["rmse_revision_pp"]==pytest.approx(np.sqrt(2/3))

def test_coverage_summary():
    x=pd.DataFrame({
      "candidate_id":["3D","3D","3E_A","3E_A"],
      "origin_id":["a","b","a","b"],
      "converged":[True,False,True,True],
      "admissible":[True,False,True,False],
    })
    y=coverage_summary(x).set_index("candidate_id")
    assert y.loc["3D","convergence_rate"]==.5
    assert y.loc["3E_A","convergence_rate"]==1.0


def test_filtered_terminal_uses_filtered_not_smoothed():
    import macropulse.slack.evaluation as ev
    idx=pd.PeriodIndex(["2020Q1","2020Q2","2020Q1","2020Q2"],freq="Q")
    x=pd.DataFrame({"estimate_class":["filtered_full_sample_parameters"]*2+["smoothed_revised"]*2,"output_gap_pct":[1.,2.,10.,20.]},index=idx)
    assert ev._filtered_terminal(x,"2020Q2")==2.0

def test_diagnostic_payload_records_root_and_ratio():
    import macropulse.slack.evaluation as ev
    class D:
        log_likelihood=1.; sigma_potential=0.; sigma_trend_growth=.001
        sigma_gap=.01; phi1=.6; phi2=-.1; converged=True
    x=ev._diagnostic_payload(D())
    assert x["trend_gap_sigma_ratio"]==pytest.approx(.1)
    assert x["min_ar_root_modulus"]>1

def test_recursive_engine_skips_left_censored_and_records_three_candidates(monkeypatch):
    import macropulse.slack.evaluation as ev
    from datetime import date
    inv=pd.DataFrame({"information_set_id":["left","ok"],"as_of_date":[date(2020,3,31),date(2020,6,30)],"panel_first_quarter":["2000Q1","2000Q1"],"panel_last_quarter":["2019Q4","2020Q1"],"complete_joint_quarters":[80,81],"source_snapshot_hash":["a","b"],"left_censored":[True,False],"admissible_for_pseudo_real_time":[False,True]})
    o=ev.PseudoRealTimeOrigin("id","2020Q1","2020-06-30","hash")
    fake=tuple(ev.EndpointResult(o,c,float(i),True,True,{}) for i,c in enumerate(ev.CANDIDATES))
    monkeypatch.setattr(ev,"evaluate_snapshot_origin",lambda *a,**k: fake)
    out=ev.recursive_pseudo_real_time_evaluation(inv,lambda d: pd.DataFrame())
    assert len(out)==3
    assert set(out.candidate_id)==set(ev.CANDIDATES)
    assert set(out.estimate_label)=={ev.ESTIMATE_LABEL}
