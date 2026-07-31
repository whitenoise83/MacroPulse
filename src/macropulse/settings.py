from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    database_path: Path = PROJECT_ROOT / "data" / "macropulse.duckdb"
    registry_path: Path = PROJECT_ROOT / "config" / "series_registry.yml"
    governance_path: Path = PROJECT_ROOT / "config" / "model_governance.yml"
    inflation_registry_path: Path = PROJECT_ROOT / "config" / "inflation_series_registry.yml"
    inflation_governance_path: Path = PROJECT_ROOT / "config" / "inflation_governance.yml"
    labour_registry_path: Path = PROJECT_ROOT / "config" / "labour_series_registry.yml"
    labour_governance_path: Path = PROJECT_ROOT / "config" / "labour_governance.yml"
    raw_data_dir: Path = PROJECT_ROOT / "data" / "raw"
    processed_data_dir: Path = PROJECT_ROOT / "data" / "processed"
    model_output_dir: Path = PROJECT_ROOT / "data" / "model_outputs"
    validation_report_dir: Path = PROJECT_ROOT / "reports" / "validation"
    fred_api_key: str = os.getenv("FRED_API_KEY", "").strip()
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)
        self.model_output_dir.mkdir(parents=True, exist_ok=True)
        self.validation_report_dir.mkdir(parents=True, exist_ok=True)

    def require_fred_api_key(self) -> str:
        if not self.fred_api_key or self.fred_api_key.startswith("replace_"):
            raise RuntimeError(
                "FRED_API_KEY is missing. Copy .env.example to .env and add your FRED API key."
            )
        return self.fred_api_key


settings = Settings()
settings.ensure_directories()
