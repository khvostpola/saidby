# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
import json
import time
from datetime import UTC, datetime, timedelta

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


def _times() -> tuple[datetime, datetime]:
    start = datetime(2026, 10, 11, 21, 27, 10, tzinfo=UTC)
    return start, start + timedelta(seconds=35)


def test_summary_line_has_total_start_finish_and_audio() -> None:
    stream = io.StringIO()
    start, finish = _times()
    Progress("human", stream=stream).summary(
        started=start, finished=finish, wall_s=35.4, audio_s=226.0, files=1, failed=0
    )
    line = stream.getvalue().strip()
    assert line == (
        "[total]    0:35   started 9:27:10 PM · finished 9:27:45 PM · 3:46 of audio at 0.16x"
    )


def test_summary_mentions_files_failures_and_the_next_day() -> None:
    stream = io.StringIO()
    start = datetime(2026, 10, 11, 23, 59, 30, tzinfo=UTC)
    Progress("human", stream=stream).summary(
        started=start,
        finished=start + timedelta(seconds=90),
        wall_s=90,
        audio_s=300,
        files=3,
        failed=1,
    )
    line = stream.getvalue()
    assert "Oct 12, 12:01:00 AM" in line
    assert "3 files" in line
    assert "1 failed" in line


def test_summary_json_event(capsys: pytest.CaptureFixture[str]) -> None:
    start, finish = _times()
    Progress("json").summary(
        started=start, finished=finish, wall_s=35.4, audio_s=226.0, files=1, failed=0
    )
    event = json.loads(capsys.readouterr().out)
    assert event["event"] == "run.end"
    assert event["wall_s"] == 35.4
    assert event["started"] == "2026-10-11T21:27:10+00:00"
    assert event["rtf"] == 0.157


def test_summary_is_silent_in_none_mode() -> None:
    stream = io.StringIO()
    start, finish = _times()
    Progress("none", stream=stream).summary(
        started=start, finished=finish, wall_s=1, audio_s=1, files=1, failed=0
    )
    assert stream.getvalue() == ""
