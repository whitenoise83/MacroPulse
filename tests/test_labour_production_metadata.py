from __future__ import annotations

import yaml

from macropulse.labour.versioning import current_labour_model_identity
from macropulse.settings import settings


def test_model1c_production_identity_and_owner_approval() -> None:
    identity = current_labour_model_identity()
    config = yaml.safe_load(
        settings.labour_governance_path.read_text(encoding="utf-8")
    )
    approval = config["model"]["approval"]
    assert identity.model_id == "US_LABOUR_NOWCAST_1C"
    assert identity.model_version == "1.0.0"
    assert identity.lifecycle_status == "production"
    assert approval["approval_phrase"] == "APPROVE MODEL 1C FREEZE"
    assert approval["candidate_validation_id"] == "0540c6ee-2d96-493a-adfe-a76c5c91cf31"
    assert approval["operational_validation_id"] == "f535fdc2-c75c-4da8-a0f8-e3d1b80416f3"
    assert approval["freeze_assessment_id"] == "7eb22dae-54c8-423e-ad1e-9977db08d388"


def test_model1c_production_policy_is_frozen() -> None:
    config = yaml.safe_load(
        settings.labour_governance_path.read_text(encoding="utf-8")
    )
    assert config["policy_candidate"]["status"] == "production_approved"
    assert config["policy_candidate"]["shadow_selector"]["role"] == "shadow_challenger_only"
    assert config["interval_candidate"]["method"] == "exp_weighted_q80"
    assert len(config["production"]["revalidation_triggers"]) >= 8
