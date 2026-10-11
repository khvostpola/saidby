# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from saidby.errors import UsageError

ENV_PREFIX = "SAIDBY_"


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: Literal["auto", "cuda", "cpu"] = "auto"
    language: str | None = None
    asr_engine: str = "faster-whisper"
    asr_model: str = "large-v3"
    compute_type: str = "auto"
    diarizer: str = "nemotron3"
    num_speakers: int | None = None
    keep_intermediates: bool = False
    force: bool = False
    fail_fast: bool = False
    strict_offline: bool = False
    progress: Literal["human", "json", "none"] = "human"

    @classmethod
    def load(
        cls, config_path: Path | None = None, overrides: dict[str, Any] | None = None
    ) -> "Settings":
        merged: dict[str, Any] = {}
        merged.update(_from_file(config_path))
        merged.update(_from_env())
        merged.update({k: v for k, v in (overrides or {}).items() if v is not None})
        try:
            return cls.model_validate(merged)
        except ValidationError as exc:
            raise UsageError(f"invalid configuration: {exc.errors()[0]['msg']}") from exc


def _config_candidates(explicit: Path | None) -> list[Path]:
    if explicit is not None:
        return [explicit]
    home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return [Path("saidby.toml"), home / "saidby" / "config.toml"]


def _from_file(explicit: Path | None) -> dict[str, Any]:
    for path in _config_candidates(explicit):
        if path.is_file():
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            section: dict[str, Any] = dict(data.get("saidby", {}))
            for table, prefix in (("asr", "asr_"), ("diarizer", "")):
                for key, value in data.get(table, {}).items():
                    section[f"{prefix}{key}" if prefix else (table if key == "engine" else key)] = (
                        value
                    )
            return section
        if explicit is not None:
            raise UsageError(f"config file not found: {path}")
    return {}


def _from_env() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in Settings.model_fields:
        value = os.environ.get(ENV_PREFIX + field.upper())
        if value is not None:
            result[field] = value
    return result
