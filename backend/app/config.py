"""
YottaFlex Complaint Intelligence Platform
Application configuration using Pydantic settings.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "YottaFlex Complaint Intelligence Platform"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: str = f"sqlite:///{BASE_DIR}/complaint_intelligence.db"
    database_echo: bool = False

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    secret_key: str = "dev-secret-key-change-in-production"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Generator defaults
    default_seed: int = 20261022
    default_scale: str = "starter"

    # Config paths
    config_dir: Path = BASE_DIR / "config"
    data_dir: Path = BASE_DIR / "data"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
