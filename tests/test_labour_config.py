from macropulse.labour.config import feature_definitions, target_definitions
from macropulse.labour.versioning import current_labour_model_identity


def test_labour_registry_has_declared_targets_and_features():
    assert [item.series_id for item in target_definitions()] == [
        "PAYEMS",
        "UNRATE",
        "CES0500000003",
    ]
    assert len(feature_definitions()) == 10


def test_labour_identity_is_development_foundation():
    identity = current_labour_model_identity()
    assert identity.model_id == "US_LABOUR_NOWCAST_1C"
    assert identity.model_version == "0.2.0"
    assert identity.lifecycle_status == "development"
    assert len(identity.config_hash) == 64
    assert len(identity.code_hash) == 64
