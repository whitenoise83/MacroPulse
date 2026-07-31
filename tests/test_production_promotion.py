from macropulse.data.repository import SCHEMA_SQL
from macropulse.governance.versioning import current_model_identity, load_governance_config


def test_production_identity_and_approval_metadata() -> None:
    identity = current_model_identity()
    governance = load_governance_config()
    approval = governance["model"]["approval"]
    assert identity.model_version == "1.0.0"
    assert identity.lifecycle_status == "production"
    assert governance["model"]["validation_source_version"] == "0.6.1"
    assert governance["production_policy"]["performance_history_version"] == "0.6.1"
    assert approval["status"] == "approved"
    assert approval["validation_id"] == "7ee34d06-f393-4fb7-90ef-6239758f8503"


def test_model_approval_registry_schema_is_present() -> None:
    assert "CREATE TABLE IF NOT EXISTS model_approvals" in SCHEMA_SQL
    assert "idx_model_approvals_version" in SCHEMA_SQL
