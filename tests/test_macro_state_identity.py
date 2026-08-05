from __future__ import annotations

from macropulse.macro_state.versioning import (
    current_macro_state_identity,
    load_macro_state_governance,
)


def test_model1d_current_development_identity() -> None:
    identity = current_macro_state_identity()
    config = load_macro_state_governance()
    assert identity.model_id == "US_MACRO_STATE_1D"
    assert identity.model_version == "0.3.8"
    assert identity.lifecycle_status == "development"
    assert len(identity.config_hash) == 64
    assert len(identity.code_hash) == 64
    assert config["required_sources"]["GDP"]["model_version"] == "1.0.0"
    assert config["required_sources"]["inflation"]["model_version"] == "1.0.0"
    assert config["required_sources"]["labour"]["model_version"] == "1.0.0"
