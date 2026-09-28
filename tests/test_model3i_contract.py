import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
C=json.loads((ROOT/"MODEL3I_PRODUCTION_HARDENING_CONTRACT.json").read_text())

def test_model3i_boundary_and_selection():
    assert C["predecessor_commit"]=="a8ebf2d05a3b49d0c21f5ab1b03ca6eefca0b094"
    assert C["predecessor_tag"]=="model3-pseudo-real-time-v1.0.0"
    assert C["selected_candidate"]=="3D"

def test_bootstrap_cannot_promote_or_retune():
    assert C["production_promotion_in_bootstrap"] is False
    assert C["database_writes_in_bootstrap"] is False
    assert C["econometric_retuning_allowed"] is False
    assert C["model1_mutation_allowed"] is False
    assert C["model2_mutation_allowed"] is False
    assert C["model3_predecessor_mutation_allowed"] is False

def test_estimate_semantics_are_explicit():
    s=C["production_estimate_semantics"]
    assert "terminal filtered_full_sample_parameters" in s["current_endpoint"]
    assert s["revised_history"]=="smoothed_revised"
    assert "not historical real-time" in s["filtered_history_not_claimed_real_time"]

def test_release_audits_are_predeclared():
    g=C["model3g_release_audits"]
    assert g["real_gdp_growth_transform_must_equal"]=="400*diff(log(GDPC1))"
    assert "variable name" in g["gdp_variable_selection"]
    assert "dense-path" in g["dense_draw_provenance"]

def test_dependency_and_release_identity():
    assert C["dependency_policy"]["requirements_statsmodels"]=="statsmodels>=0.14.6,<0.16"
    assert C["dependency_policy"]["pyproject_normalization_required"] is True
    assert C["release_tag_planned"]=="model3-potential-output-v1.0.0"
