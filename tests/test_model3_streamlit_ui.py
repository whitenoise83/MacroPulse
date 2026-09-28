from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_model3_streamlit_page_is_registered() -> None:
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'st.Page("ui/model3_slack.py"' in text
    assert 'title="Potential Output & Slack"' in text


def test_model3_streamlit_page_uses_governed_production_wrapper() -> None:
    text = (ROOT / "ui" / "model3_slack.py").read_text(encoding="utf-8")
    assert "production_current_estimate" in text
    assert "deterministic_export_hash" in text
    assert "MODEL3_SELECTED_CANDIDATE" in text
    assert "PRODUCTION_CURRENT_CLASS" in text
    assert "REVISED_HISTORY_CLASS" in text


def test_model3_streamlit_page_preserves_estimate_class_semantics() -> None:
    text = (ROOT / "ui" / "model3_slack.py").read_text(encoding="utf-8")
    assert "revised-history outputs" in text
    assert "must not be interpreted as real-time estimates" in text
    assert "smoothed historical path" in text
    assert "not a pseudo-real-time sequence" in text


def test_model3_streamlit_page_is_read_only() -> None:
    text = (ROOT / "ui" / "model3_slack.py").read_text(encoding="utf-8")
    forbidden = (
        "save_model_outputs(",
        "INSERT INTO",
        "UPDATE ",
        "DELETE FROM",
        "replace_historical_snapshot(",
    )
    for value in forbidden:
        assert value not in text
