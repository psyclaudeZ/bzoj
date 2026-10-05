"""Deployment branding, independent of internal package and storage names."""

import os
from pathlib import Path
import tomllib

from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT = Path(__file__).resolve().parent.parent


class SiteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def clean_name(cls, name: str) -> str:
        name = name.strip()
        if not name or any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise ValueError("Site name must be nonblank and contain no control characters.")
        return name


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    site: SiteConfig


def load_settings(path: Path | None = None) -> Settings:
    if path is None:
        # OJ_CONFIG can select an untracked, deployment-specific config file.
        path = ROOT / os.environ.get("OJ_CONFIG", "config.toml")
    with path.open("rb") as stream:
        return Settings.model_validate(tomllib.load(stream))
