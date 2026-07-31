from __future__ import annotations

import yaml

from macropulse.inflation.versioning import current_inflation_model_identity
from macropulse.settings import settings


def test_model1b_production_identity_and_owner_approval() -> None:
    identity = current_inflation_model_identity()
    config = yaml.safe_load(settings.inflation_governance_path.read_text(encoding="utf-8"))
    model = config["model"]
    approval = model["approval"]

    assert identity.model_id == "US_INFLATION_NOWCAST_1B"
    assert identity.model_version == "1.0.0"
    assert identity.lifecycle_status == "production"
    assert model["production_status"] == "production"
    assert approval["status"] == "approved"
    assert approval["approval_phrase"] == "APPROVE MODEL 1B FREEZE"
    assert approval["candidate_validation_id"] == "5f0cd6ea-c41f-44da-a21a-43490d8e75ce"
    assert approval["operational_validation_id"] == "58c89931-0f6b-43ed-8815-abbc99fa4ac8"
    assert approval["freeze_assessment_id"] == "2b7fe987-384a-451b-971f-03d5bf5106c7"
    assert approval["freeze_readiness"] == "ready_for_model_owner_signoff"


def test_model1b_production_policy_and_shadow_roles_are_frozen() -> None:
    config = yaml.safe_load(settings.inflation_governance_path.read_text(encoding="utf-8"))
    assert config["policy_candidate"]["status"] == "production_approved"
    assert config["policy_candidate"]["shadow_selector"]["role"] == "shadow_challenger_only"
    assert config["interval_candidate"]["status"] == "production_approved"
    assert config["interval_candidate"]["method"] == "exp_weighted_q80"
    assert config["production"]["point_policy"] == "stable_map"
    assert config["production"]["shadow_policy"] == "adaptive_shadow_only"
    assert len(config["production"]["revalidation_triggers"]) >= 8
