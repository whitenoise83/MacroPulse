from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "ui" / "model2_bvar.py"


def test_model2_streamlit_page_is_registered() -> None:
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'st.Page("ui/model2_bvar.py"' in text
    assert 'title="Bayesian VAR Forecasts & Scenarios"' in text


def test_model2_streamlit_page_uses_frozen_production_interface() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "run_model2_forecast" in text
    assert "selected_candidate" in text
    assert "MODEL2_RELEASE.json" in text
    assert "model2-bvar-v1.0.2" in text


def test_model2_streamlit_page_exposes_governed_outputs() -> None:
    text = PAGE.read_text(encoding="utf-8")
    for value in (
        "Posterior predictive distributions",
        "Impulse-response functions",
        "Forecast-error variance decomposition",
        "Deterministic conditional path scenario",
        "Production provenance",
    ):
        assert value in text


def test_model2_streamlit_page_preserves_scenario_semantics() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "mechanical, not a Bayesian conditional density" in text
    assert "not a probability statement" in text
    assert "not an independent causal claim" in text


def test_model2_streamlit_page_is_read_only() -> None:
    text = PAGE.read_text(encoding="utf-8")
    for forbidden in (
        "save_model_outputs(",
        "INSERT INTO",
        "UPDATE ",
        "DELETE FROM",
        "replace_historical_snapshot(",
    ):
        assert forbidden not in text
