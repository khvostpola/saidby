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
    deterministic: bool = False
    diarizer: str = "nemotron3"
    num_speakers: int | None = None
    directory: Path | None = None
    identify: bool = True
    identify_threshold: float = 0.5
    identify_min_speech: float = 3.0
    embedder: str = "wespeaker-resnet34"
    bias: bool = True
    transplant: bool = True
    correct: bool = False
    llm_url: str | None = None
    llm_binary: str | None = None
    llm_model: str = "qwen3.5-9b-q4"
    llm_context: int = 8192
    chunk_words: int = 90
    allow_remote_llm: bool = False
    compare: str | None = None
    bias_mode: Literal["full", "windows"] = "full"
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
            first = exc.errors()[0]
            where = ".".join(str(part) for part in first["loc"])
            raise UsageError(f"invalid configuration: {where}: {first['msg']}") from exc


def _config_candidates(explicit: Path | None) -> list[Path]:
    if explicit is not None:
        return [explicit]
    home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return [Path("saidby.toml"), home / "saidby" / "config.toml"]


TABLE_KEYS: dict[str, dict[str, str]] = {
    "asr": {
        "engine": "asr_engine",
        "model": "asr_model",
        "compute_type": "compute_type",
        "deterministic": "deterministic",
    },
    "diarizer": {"engine": "diarizer", "num_speakers": "num_speakers", "compare": "compare"},
    "identify": {
        "enabled": "identify",
        "threshold": "identify_threshold",
        "min_speech_s": "identify_min_speech",
        "embedder": "embedder",
    },
    "glossary": {
        "directory": "directory",
        "bias": "bias",
        "bias_mode": "bias_mode",
        "transplant": "transplant",
        "correct": "correct",
    },
    "llm": {
        "url": "llm_url",
        "binary": "llm_binary",
        "model": "llm_model",
        "context": "llm_context",
        "chunk_words": "chunk_words",
        "allow_remote": "allow_remote_llm",
    },
}
PATH_FIELDS = ("directory",)


def _flatten(data: dict[str, Any], source: Path) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for table, values in data.items():
        if table == "saidby":
            unknown = sorted(set(values) - set(Settings.model_fields))
            if unknown:
                raise UsageError(f"{source}: unknown key(s) in [saidby]: {', '.join(unknown)}")
            flat.update(values)
        elif table in TABLE_KEYS:
            mapping = TABLE_KEYS[table]
            unknown = sorted(set(values) - set(mapping))
            if unknown:
                valid = ", ".join(sorted(mapping))
                raise UsageError(
                    f"{source}: unknown key(s) in [{table}]: {', '.join(unknown)} (valid: {valid})"
                )
            flat.update({mapping[key]: value for key, value in values.items()})
        else:
            valid = ", ".join(["saidby", *TABLE_KEYS])
            raise UsageError(f"{source}: unknown section [{table}] (valid: {valid})")
    for field in PATH_FIELDS:
        if isinstance(flat.get(field), str) and not Path(flat[field]).is_absolute():
            flat[field] = str(source.parent / flat[field])
    return flat


def _from_file(explicit: Path | None) -> dict[str, Any]:
    for path in _config_candidates(explicit):
        if path.is_file():
            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as exc:
                raise UsageError(f"{path}: not valid TOML: {exc}") from exc
            return _flatten(data, path)
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
