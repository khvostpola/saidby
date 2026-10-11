# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from saidby.schema.manifest import StageRecord
from saidby.telemetry.runlog import RunLog
from saidby.telemetry.sink import TelemetrySink


@dataclass
class Recording:
    index: int
    media: Path
    slug: str
    out_dir: Path
    log: RunLog
    telemetry: TelemetrySink
    stages: list[StageRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: Literal["ok", "failed", "interrupted"] = "ok"
    failed_stage: str | None = None
    error_type: str | None = None
    error: str | None = None
    exit_code: int = 0
    source_sha256: str = ""
    size_bytes: int = 0
    duration_s: float = 0.0
    created_at: datetime | None = None
    glossary: dict[str, Any] = field(default_factory=dict)

    @property
    def work_dir(self) -> Path:
        return self.out_dir / ".work"

    @property
    def wav(self) -> Path:
        return self.work_dir / "audio.wav"

    @property
    def alive(self) -> bool:
        return self.status == "ok"


@dataclass(frozen=True)
class RecordingResult:
    slug: str
    out_dir: Path
    status: str
    exit_code: int
    error_type: str | None = None


@dataclass(frozen=True)
class TextArtifact:
    path: Path
    key: str
