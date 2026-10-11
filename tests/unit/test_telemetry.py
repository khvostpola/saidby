# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from saidby.schema.telemetry import ALLOWED_FIELDS, TelemetryEvent
from saidby.telemetry import TelemetrySink


def test_allowed_fields_are_frozen() -> None:
    assert set(TelemetryEvent.model_fields) == set(ALLOWED_FIELDS)


def test_sink_writes_one_json_line(tmp_path: Path) -> None:
    sink = TelemetrySink(tmp_path / "logs" / "telemetry.jsonl")
    sink.emit(
        "stage.end",
        stage="asr",
        engine="faster-whisper",
        model="asr:large-v3",
        device="cuda",
        wall_s=1.5,
        rtf=0.1,
    )
    lines = (tmp_path / "logs" / "telemetry.jsonl").read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "stage.end"
    assert record["tool_version"]
    assert "words" not in record


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    sink = TelemetrySink(tmp_path / "t.jsonl")
    with pytest.raises(ValidationError):
        sink.emit("stage.end", transcript="free text")


def test_free_text_cannot_enter_string_fields(tmp_path: Path) -> None:
    sink = TelemetrySink(tmp_path / "t.jsonl")
    with pytest.raises(ValidationError):
        sink.emit("stage.error", error_type="could not open /home/someone/call.m4a")
    with pytest.raises(ValidationError):
        sink.emit("stage.end", model="A Person Name")
