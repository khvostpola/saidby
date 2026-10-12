# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
import json
import time

import pytest

from saidby.cli.progress import CLEAR, Progress


class Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def _end(progress: Progress, stage: str = "asr") -> None:
    progress.stage_end(
        index=1,
        total=1,
        slug="call",
        stage=stage,
        parts=["engine"],
        wall_s=1.0,
        rtf=None,
        cached=False,
    )


def test_slow_stage_shows_a_live_line_then_the_final_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "xterm")
    stream = Tty()
    progress = Progress("human", stream=stream, delay_s=0.05, interval_s=0.05)
    progress.stage_start(index=1, total=1, slug="call", stage="asr")
    time.sleep(0.3)
    _end(progress)
    text = stream.getvalue()
    assert "[1/1] asr" in text
    assert "transcribing..." in text
    assert text.count("transcribing...") >= 2
    assert text.rstrip().endswith("engine   0:01")
    assert text.index(CLEAR) < text.index("engine   0:01")


def test_fast_stage_never_flashes_a_live_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "xterm")
    stream = Tty()
    progress = Progress("human", stream=stream, delay_s=0.5, interval_s=0.5)
    progress.stage_start(index=1, total=1, slug="call", stage="ingest")
    _end(progress, "ingest")
    assert "converting" not in stream.getvalue()
    assert stream.getvalue().count("\n") == 1


def test_no_live_line_when_not_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "xterm")
    stream = io.StringIO()
    progress = Progress("human", stream=stream, delay_s=0.01, interval_s=0.01)
    progress.stage_start(index=1, total=1, slug="call", stage="asr")
    time.sleep(0.1)
    _end(progress)
    assert "transcribing" not in stream.getvalue()
    assert "\x1b" not in stream.getvalue()


def test_stop_clears_a_pending_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "xterm")
    stream = Tty()
    progress = Progress("human", stream=stream, delay_s=0.02, interval_s=0.02)
    progress.stage_start(index=1, total=1, slug="call", stage="diarize")
    time.sleep(0.15)
    progress.stop()
    assert stream.getvalue().endswith(CLEAR)
    progress.stop()


def test_json_mode_announces_the_start(capsys: pytest.CaptureFixture[str]) -> None:
    progress = Progress("json")
    progress.stage_start(index=1, total=1, slug="call", stage="asr")
    event = json.loads(capsys.readouterr().out)
    assert event == {"event": "stage.start", "file": "call", "stage": "asr"}
