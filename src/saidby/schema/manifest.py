# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from saidby.schema.engine import EngineInfo
from saidby.schema.speakers import SpeakerEntry
from saidby.schema.telemetry import StageName


class StageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: StageName
    engine: EngineInfo | None = None
    options: dict[str, str | int | float | bool | None] = {}
    wall_s: float = 0.0
    cached: bool = False
    status: Literal["ok", "failed", "skipped"] = "ok"


class SourceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    size_bytes: int
    duration_s: float


class AudioInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_rate: int = 16000
    channels: int = 1
    duration_s: float


class DeviceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested: str
    used: str
    name: str | None = None
    vram_total_mb: int | None = None
    reason: str | None = None


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal["saidby.manifest/1"] = Field(default="saidby.manifest/1", alias="schema")
    tool: dict[str, str]
    run_id: str
    status: Literal["ok", "failed", "interrupted"]
    created_at: datetime
    finished_at: datetime | None = None
    source: SourceInfo
    audio: AudioInfo
    language: str | None = None
    device: DeviceRecord
    stages: list[StageRecord] = []
    speakers: list[SpeakerEntry] = []
    files: dict[str, Any] = {}
    directory: dict[str, Any] | None = None
    glossary: dict[str, Any] | None = None
    compare: dict[str, Any] | None = None
    edits: list[dict[str, Any]] = []
    warnings: list[str] = []
    failed_stage: str | None = None
    error_type: str | None = None
    error: str | None = None
