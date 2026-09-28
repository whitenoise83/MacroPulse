import pytest
from macropulse.slack.model1_integration import align_current_state, preserve_provenance, validate_model3_estimate_class

def row(): return {'model_name':'DFM','model_version':'0.5.0','forecast_date':'2026-04-29','target_period':'2026Q1','information_set_hash':'abc','created_at':'x','point_forecast':2.4}
def test_provenance_preserved_not_value_payload():
    p=preserve_provenance(row()); assert p['model_name']=='DFM' and 'point_forecast' not in p
def test_exact_alignment(): assert align_current_state(row(),target_period='2026Q1',forecast_date='2026-04-29',information_set_hash='abc').aligned
def test_mismatch_is_explicit():
    r=align_current_state(row(),information_set_hash='different'); assert not r.aligned and r.diagnostics==('mismatch:information_set_hash',)
def test_missing_is_explicit():
    r=align_current_state({'target_period':'2026Q1'},information_set_hash='x'); assert not r.aligned and 'missing:information_set_hash' in r.diagnostics
def test_full_sample_filtered_not_strict_real_time():
    with pytest.raises(ValueError): validate_model3_estimate_class('filtered_full_sample_parameters',claim_strict_real_time=True)
def test_smoothed_not_strict_real_time():
    with pytest.raises(ValueError): validate_model3_estimate_class('smoothed_revised',claim_strict_real_time=True)
def test_research_label_allowed_without_real_time_claim(): validate_model3_estimate_class('smoothed_revised',claim_strict_real_time=False)
