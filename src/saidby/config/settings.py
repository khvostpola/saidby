# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, PrivateAttr, ValidationError, field_validator

from saidby.errors import UsageError
from saidby.i18n import _

ENV_PREFIX = "SAIDBY_"
ORIGIN_ENV = "env"
ORIGIN_FLAG = "flag"


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
    directory: list[Path] = []
    terms: list[str] = []
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
    _origins: dict[str, str] = PrivateAttr(default_factory=dict)

    @field_validator("directory", mode="before")
    @classmethod
    def _directory_list(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str | Path):
            return [value]
        return value

    @property
    def sources(self) -> list[Path]:
        return list(self._sources)

    @property
    def origins(self) -> dict[str, str]:
        return dict(self._origins)

    @classmethod
    def load(
        cls, config_path: Path | None = None, overrides: dict[str, Any] | None = None
    ) -> "Settings":
        files = config_files(config_path)
        merged: dict[str, Any] = {}
        origins: dict[str, str] = {}
        for path in files:
            flat = _read_file(path)
            _layer(merged, flat)
            origins.update(dict.fromkeys(flat, str(path)))
        from_env = _from_env()
        merged.update(from_env)
        origins.update(dict.fromkeys(from_env, ORIGIN_ENV))
        flags = {k: v for k, v in (overrides or {}).items() if v is not None}
        merged.update(flags)
        origins.update(dict.fromkeys(flags, ORIGIN_FLAG))
        try:
            settings = cls.model_validate(merged)
        except ValidationError as exc:
            first = exc.errors()[0]
            where = ".".join(str(part) for part in first["loc"])
            raise UsageError(
                _("invalid configuration: {where}: {msg}").format(where=where, msg=first["msg"])
            ) from exc
        settings._sources = files
        settings._origins = origins
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
            raise UsageError(_("config file not found: {explicit}").format(explicit=explicit))
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
        "terms": "terms",
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


def _flatten(data: dict[str, Any], source: Path) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for table, values in data.items():
        if table == "saidby":
            unknown = sorted(set(values) - set(Settings.model_fields))
            if unknown:
                raise UsageError(
                    _("{source}: unknown key(s) in [saidby]: {items}").format(
                        source=source, items=", ".join(unknown)
                    )
                )
            flat.update(values)
        elif table in TABLE_KEYS:
            mapping = TABLE_KEYS[table]
            unknown = sorted(set(values) - set(mapping))
            if unknown:
                valid = ", ".join(sorted(mapping))
                raise UsageError(
                    _("{source}: unknown key(s) in [{table}]: {items} (valid: {valid})").format(
                        source=source, table=table, items=", ".join(unknown), valid=valid
                    )
                )
            flat.update({mapping[key]: value for key, value in values.items()})
        else:
            valid = ", ".join(["saidby", *TABLE_KEYS])
            raise UsageError(
                _("{source}: unknown section [{table}] (valid: {valid})").format(
                    source=source, table=table, valid=valid
                )
            )
    _resolve_paths(flat, source)
    return flat


def _resolve_paths(flat: dict[str, Any], source: Path) -> None:
    directory = flat.get("directory")
    if directory is not None:
        items = [directory] if isinstance(directory, str) else directory
        if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
            raise UsageError(
                _("{source}: directory must be a path or a list of paths").format(source=source)
            )
        flat["directory"] = [_anchor(item, source) for item in items]
    out = flat.get("out")
    if isinstance(out, str) and source != global_config_path():
        flat["out"] = _anchor(out, source)


def _anchor(item: str, source: Path) -> str:
    path = Path(item).expanduser()
    return str(path if path.is_absolute() else source.parent / path)


def _layer(merged: dict[str, Any], flat: dict[str, Any]) -> None:
    for key, value in flat.items():
        if key == "directory":
            earlier = merged.get(key, [])
            merged[key] = [*earlier, *(item for item in value if item not in earlier)]
        else:
            merged[key] = value


def _read_file(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise UsageError(_("{path}: not valid TOML: {exc}").format(path=path, exc=exc)) from exc
    return _flatten(data, path)


def _from_env() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in Settings.model_fields:
        value = os.environ.get(ENV_PREFIX + field.upper())
        if value is None:
            continue
        if field == "directory":
            result[field] = [v for v in value.split(os.pathsep) if v]
        elif field == "terms":
            result[field] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            result[field] = value
    return result
