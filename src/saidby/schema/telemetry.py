# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EventName = Literal[
    "run.start",
    "run.end",
    "file.start",
    "file.end",
    "stage.start",
    "stage.end",
    "stage.skip",
    "stage.error",
    "model.load",
    "model.unload",
]
StageName = Literal[
    "ingest",
    "asr",
    "asr_bias",
    "transplant",
    "diarize",
    "compare",
    "identify",
    "correct",
    "align",
    "tracks",
    "outputs",
]

ALLOWED_FIELDS = (
    "event",
    "ts",
    "run_id",
    "tool_version",
    "file_index",
    "files_total",
    "stage",
    "engine",
    "model",
    "revision",
    "device",
    "compute_type",
    "mode",
    "audio_s",
    "wall_s",
    "rtf",
    "model_load_s",
    "vram_peak_mb",
    "cached",
    "status",
    "error_type",
    "exit_code",
    "segments",
    "words",
    "speakers",
    "turns",
    "speech_s",
    "overlap_s",
    "hotwords_tokens",
    "hotwords_truncated",
    "bias_windows",
    "bias_window_s",
    "transplant_swaps",
    "dialect_swaps",
    "llm_chunks",
    "llm_accepted",
    "llm_rejected",
    "llm_truncated",
    "identified",
    "unidentified",
    "voiceprints_skipped",
    "compare_engine",
    "agreement",
    "disagreement_s",
    "disagreement_spans",
    "python",
    "platform",
)


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: EventName
    ts: str
    run_id: str = Field(pattern=r"^[0-9a-f-]{8,36}$")
    tool_version: str
    file_index: int | None = None
    files_total: int | None = None
    stage: StageName | None = None
    engine: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    model: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9._:-]*$")
    revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{7,40}$")
    device: Literal["cuda", "cpu"] | None = None
    compute_type: str | None = Field(default=None, pattern=r"^[a-z0-9_]+$")
    mode: str | None = Field(default=None, pattern=r"^[a-z_]+$")
    audio_s: float | None = None
    wall_s: float | None = None
    rtf: float | None = None
    model_load_s: float | None = None
    vram_peak_mb: int | None = None
    cached: bool | None = None
    status: Literal["ok", "failed", "interrupted"] | None = None
    error_type: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_.]*$")
    exit_code: int | None = None
    segments: int | None = None
    words: int | None = None
    speakers: int | None = None
    turns: int | None = None
    speech_s: float | None = None
    overlap_s: float | None = None
    hotwords_tokens: int | None = None
    hotwords_truncated: bool | None = None
    bias_windows: int | None = None
    bias_window_s: float | None = None
    transplant_swaps: int | None = None
    dialect_swaps: int | None = None
    llm_chunks: int | None = None
    llm_accepted: int | None = None
    llm_rejected: int | None = None
    llm_truncated: int | None = None
    identified: int | None = None
    unidentified: int | None = None
    voiceprints_skipped: int | None = None
    compare_engine: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    agreement: float | None = None
    disagreement_s: float | None = None
    disagreement_spans: int | None = None
    python: str | None = None
    platform: str | None = None
