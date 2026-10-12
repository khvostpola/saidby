# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, PrivateAttr, ValidationError

from saidby.errors import UsageError

ENV_PREFIX = "SAIDBY_"


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    out: Path = Path("saidby")
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

    _sources: list[Path] = PrivateAttr(default_factory=list)

    @property
    def sources(self) -> list[Path]:
        return list(self._sources)

    @classmethod
    def load(
        cls, config_path: Path | None = None, overrides: dict[str, Any] | None = None
    ) -> "Settings":
        files = config_files(config_path)
        merged: dict[str, Any] = {}
        for path in files:
            merged.update(_read_file(path))
        merged.update(_from_env())
        merged.update({k: v for k, v in (overrides or {}).items() if v is not None})
        try:
            settings = cls.model_validate(merged)
        except ValidationError as exc:
            first = exc.errors()[0]
            where = ".".join(str(part) for part in first["loc"])
            raise UsageError(f"invalid configuration: {where}: {first['msg']}") from exc
        settings._sources = files
        return settings


def global_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "saidby" / "config.toml"


def find_project_config(start: Path | None = None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    home = Path.home().resolve()
    inside_home = here == home or home in here.parents
    for directory in [here, *here.parents] if inside_home else [here]:
        candidate = directory / "saidby.toml"
        if candidate.is_file():
            return candidate
        if directory == home:
            break
    return None


def config_files(explicit: Path | None = None) -> list[Path]:
    if explicit is not None:
        if not explicit.is_file():
            raise UsageError(f"config file not found: {explicit}")
        return [explicit]
    files: list[Path] = []
    for path in (global_config_path(), find_project_config()):
        if path is not None and path.is_file() and path not in files:
            files.append(path)
    return files


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
PATH_FIELDS = ("directory", "out")


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
        relative_to_file = field != "out" or source != global_config_path()
        value = flat.get(field)
        if relative_to_file and isinstance(value, str) and not Path(value).is_absolute():
            flat[field] = str(source.parent / value)
    return flat


def _read_file(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise UsageError(f"{path}: not valid TOML: {exc}") from exc
    return _flatten(data, path)


def _from_env() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in Settings.model_fields:
        value = os.environ.get(ENV_PREFIX + field.upper())
        if value is not None:
            result[field] = value
    return result
