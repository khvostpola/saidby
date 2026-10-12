# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
import json
import time
from datetime import UTC, datetime, timedelta

import pytest

from saidby.cli.progress import CLEAR, Progress
from saidby.cli.term import Terminal
from saidby.runtime.device import DeviceInfo
from saidby.runtime.usage import CpuUsage, GpuUsage


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


def test_a_startup_phase_shows_a_live_line_and_leaves_nothing_behind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TERM", "xterm")
    stream = Tty()
    progress = Progress("human", stream=stream, delay_s=0.02, interval_s=0.02)
    with progress.phase("device", "checking the GPU"):
        time.sleep(0.15)
    text = stream.getvalue()
    assert "device      checking the GPU...  0:00" in text
    assert text.endswith(CLEAR)
    assert "\n" not in text


def test_a_quick_phase_never_flashes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "xterm")
    stream = Tty()
    progress = Progress("human", stream=stream, delay_s=0.5, interval_s=0.5)
    with progress.phase("starting", "loading PyTorch"):
        pass
    assert stream.getvalue() == ""


def test_phases_print_nothing_when_not_a_terminal() -> None:
    stream = io.StringIO()
    progress = Progress("human", stream=stream, delay_s=0.01, interval_s=0.01)
    with progress.phase("device", "checking the GPU"):
        time.sleep(0.05)
    assert stream.getvalue() == ""


def test_the_device_line_is_printed_in_human_mode() -> None:
    stream = io.StringIO()
    Progress("human", stream=stream).device(DeviceInfo("cpu", reason="no_gpu"), "auto")
    assert "(auto → cpu: no NVIDIA GPU found)" in stream.getvalue()


def test_json_mode_announces_the_run_and_the_device(capsys: pytest.CaptureFixture[str]) -> None:
    progress = Progress("json")
    progress.run_start()
    progress.device(DeviceInfo("cuda", "Test GPU", 8188), "auto")
    first, second = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert first["event"] == "run.start"
    assert first["saidby"]
    assert second == {
        "event": "device",
        "requested": "auto",
        "used": "cuda",
        "name": "Test GPU",
        "vram_total_mb": 8188,
        "reason": None,
    }


def test_none_mode_stays_silent(capsys: pytest.CaptureFixture[str]) -> None:
    progress = Progress("none")
    progress.run_start()
    progress.device(DeviceInfo("cpu", reason="no_gpu"), "auto")
    with progress.phase("device", "checking the GPU"):
        pass
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "")


def _live(monkeypatch: pytest.MonkeyPatch, **terminal: object) -> tuple[Tty, Progress]:
    monkeypatch.setenv("TERM", "xterm")
    stream = Tty()
    term = Terminal(**{"tty": True, "color": False, "truecolor": False, "columns": 100, **terminal})  # type: ignore[arg-type]
    return stream, Progress("human", stream=stream, delay_s=0.01, interval_s=0.02, terminal=term)


def test_the_live_text_goes_from_loading_to_running(monkeypatch: pytest.MonkeyPatch) -> None:
    stream, progress = _live(monkeypatch)
    progress.track_usage(DeviceInfo("cuda", "GPU", 8192), None)
    progress.stage_start(index=1, total=1, slug="call", stage="asr")
    progress.loading("large-v3")
    time.sleep(0.12)
    progress.running()
    time.sleep(0.12)
    progress.stop()
    text = stream.getvalue()
    assert "loading large-v3 into the GPU...  0:00" in text
    assert "transcribing...  0:00" in text
    assert text.index("loading large-v3") < text.index("transcribing")


def test_loading_on_the_cpu_does_not_mention_the_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    stream, progress = _live(monkeypatch)
    progress.track_usage(DeviceInfo("cpu", reason="no_gpu"), None)
    progress.stage_start(index=1, total=1, slug="call", stage="diarize")
    progress.loading("nemotron3")
    time.sleep(0.1)
    progress.stop()
    assert "loading nemotron3...  " in stream.getvalue()
    assert "GPU" not in stream.getvalue()


def test_the_live_line_shows_what_the_device_is_doing(monkeypatch: pytest.MonkeyPatch) -> None:
    stream, progress = _live(monkeypatch)
    progress.track_usage(DeviceInfo("cuda", "GPU", 8192), lambda: GpuUsage(5222, 8192, 93))
    progress.stage_start(index=1, total=1, slug="call", stage="asr")
    time.sleep(0.12)
    progress.stop()
    assert "transcribing...  0:00  ·  GPU 5.1/8.0 GB · 93%" in stream.getvalue()


def test_the_usage_is_dimmed_when_there_is_color(monkeypatch: pytest.MonkeyPatch) -> None:
    stream, progress = _live(monkeypatch, color=True)
    progress.track_usage(DeviceInfo("cpu", reason="no_gpu"), lambda: CpuUsage(8, 94))
    progress.stage_start(index=1, total=1, slug="call", stage="asr")
    time.sleep(0.12)
    progress.stop()
    assert "\x1b[2m  ·  CPU 8 threads · 94%\x1b[0m" in stream.getvalue()


def test_the_usage_is_dropped_before_the_line_would_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    stream, progress = _live(monkeypatch, columns=45)
    progress.track_usage(DeviceInfo("cuda", "GPU", 8192), lambda: GpuUsage(1024, 8192, 10))
    progress.stage_start(index=1, total=1, slug="call", stage="asr")
    time.sleep(0.12)
    progress.stop()
    assert "transcribing..." in stream.getvalue()
    assert "GPU 1.0" not in stream.getvalue()


def test_a_failing_probe_never_breaks_the_line(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> GpuUsage:
        raise RuntimeError("nvidia-smi vanished")

    stream, progress = _live(monkeypatch)
    progress.track_usage(DeviceInfo("cuda", "GPU", 8192), broken)
    progress.stage_start(index=1, total=1, slug="call", stage="asr")
    time.sleep(0.1)
    progress.stop()
    assert "transcribing..." in stream.getvalue()
    assert "RuntimeError" not in stream.getvalue()


def test_phases_never_show_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    stream, progress = _live(monkeypatch)
    progress.track_usage(DeviceInfo("cuda", "GPU", 8192), lambda: GpuUsage(1024, 8192, 10))
    with progress.phase("device", "checking the GPU"):
        time.sleep(0.1)
    assert "GPU 1.0" not in stream.getvalue()


def test_json_mode_announces_a_model_load(capsys: pytest.CaptureFixture[str]) -> None:
    progress = Progress("json")
    progress.stage_start(index=1, total=1, slug="call", stage="asr")
    progress.loading("large-v3")
    progress.running()
    events = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert events[-1] == {
        "event": "stage.loading",
        "file": "call",
        "stage": "asr",
        "model": "large-v3",
    }
