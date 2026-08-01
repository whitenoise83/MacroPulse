from __future__ import annotations

from macropulse.macro_state.engine import (
    classify_regime,
    piecewise_score,
)


def test_piecewise_score_interpolates_and_clamps() -> None:
    anchors = [[0.0, -2.0], [2.0, 0.0], [4.0, 2.0]]
    assert piecewise_score(-1.0, anchors) == -2.0
    assert piecewise_score(5.0, anchors) == 2.0
    assert piecewise_score(1.0, anchors) == -1.0
    assert piecewise_score(3.0, anchors) == 1.0


def test_regime_classifier_covers_canonical_states() -> None:
    assert classify_regime(-1.0, 1.0, 0.0)[0] == "stagflation_risk"
    assert classify_regime(-1.0, 0.0, -1.0)[0] == "hard_landing_risk"
    assert classify_regime(1.0, 1.0, 1.0)[0] == "overheating"
    assert (
        classify_regime(0.5, -0.5, 0.0)[0]
        == "disinflationary_expansion"
    )
    assert classify_regime(0.1, 0.1, 0.1)[0] == "balanced_expansion"
