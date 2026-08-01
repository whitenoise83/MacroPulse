import yaml

from macropulse.data.repository import MacroRepository
from macropulse.governance.versioning import current_model_identity
from macropulse.inflation.versioning import current_inflation_model_identity
from macropulse.labour.versioning import current_labour_model_identity
from macropulse.macro_state.versioning import current_macro_state_identity
from macropulse.settings import settings


def main() -> None:
    repository = MacroRepository()
    repository.initialise()

    gdp_identity = current_model_identity().as_dict()
    production_config = yaml.safe_load(settings.governance_path.read_text(encoding="utf-8"))["model"]
    gdp_identity["config_hash"] = str(production_config.get("approved_config_hash", gdp_identity["config_hash"]))
    gdp_identity["code_hash"] = str(production_config.get("approved_code_hash", gdp_identity["code_hash"]))
    repository.register_model_identity(
        gdp_identity,
        notes="Approved Model 1A production identity; hashes preserved from owner-approved freeze.",
    )

    inflation_identity = current_inflation_model_identity()
    repository.register_model_identity(
        inflation_identity.as_dict(),
        notes=(
            f"Model 1B v{inflation_identity.model_version} "
            f"{inflation_identity.lifecycle_status} identity."
        ),
    )

    labour_identity = current_labour_model_identity()
    repository.register_model_identity(
        labour_identity.as_dict(),
        notes=(
            f"Model 1C v{labour_identity.model_version} "
            f"{labour_identity.lifecycle_status} identity."
        ),
    )
    macro_state_identity = current_macro_state_identity()
    repository.register_model_identity(
        macro_state_identity.as_dict(),
        notes=(
            f"Model 1D v{macro_state_identity.model_version} "
            f"{macro_state_identity.lifecycle_status} identity."
        ),
    )
    print(f"Database initialised: {repository.database_path}")
    print(
        f"Model registered: {gdp_identity['model_id']} v{gdp_identity['model_version']} "
        f"({gdp_identity['lifecycle_status']})"
    )
    print(
        f"Model registered: {inflation_identity.model_id} v{inflation_identity.model_version} "
        f"({inflation_identity.lifecycle_status})"
    )
    print(
        f"Model registered: {labour_identity.model_id} v{labour_identity.model_version} "
        f"({labour_identity.lifecycle_status})"
    )
    print(f"Inflation configuration hash: {inflation_identity.config_hash[:12]}...")
    print(f"Inflation code hash: {inflation_identity.code_hash[:12]}...")
    print(f"Labour configuration hash: {labour_identity.config_hash[:12]}...")
    print(f"Labour code hash: {labour_identity.code_hash[:12]}...")
    print(
        f"Model registered: {macro_state_identity.model_id} "
        f"v{macro_state_identity.model_version} "
        f"({macro_state_identity.lifecycle_status})"
    )
    print(
        f"Macro-state configuration hash: "
        f"{macro_state_identity.config_hash[:12]}..."
    )
    print(
        f"Macro-state code hash: "
        f"{macro_state_identity.code_hash[:12]}..."
    )


if __name__ == "__main__":
    main()
