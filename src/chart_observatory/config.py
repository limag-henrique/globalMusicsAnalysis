from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CountryConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=2, max_length=2)
    name: str = Field(min_length=1)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized.isalpha() or not normalized.isascii():
            raise ValueError("country code must contain two ASCII letters")
        return normalized


class ResearchWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_date: date
    end_date: date | None = None
    default_temporal_alignment: str

    @model_validator(mode="after")
    def validate_order(self) -> ResearchWindow:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("research end date must not precede start date")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHART_OBSERVATORY_",
        env_file=".env",
        extra="ignore",
    )

    countries: tuple[CountryConfig, ...]
    research: ResearchWindow
    database_url: str = (
        "postgresql+psycopg://chart_observatory:local_development_only"
        "@localhost:5432/chart_observatory"
    )
    artifact_root: Path = Path("data/raw")
    config_root: Path = Path("config")
    log_level: str = "INFO"

    @classmethod
    def load(cls, project_root: Path) -> Settings:
        country_data = _load_yaml(project_root / "config" / "countries.yaml")
        research_data = _load_yaml(project_root / "config" / "research.yaml")
        return cls(
            countries=tuple(country_data["countries"]),
            research=research_data["research"],
        )


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"configuration root must be a mapping: {path}")
    return data
