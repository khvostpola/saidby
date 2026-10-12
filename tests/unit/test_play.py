# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import subprocess
from pathlib import Path
from typing import Any

import pytest

from saidby.runtime import diagnose, procs


class _Process:
    def __init__(self, interrupt: bool = False) -> None:
        self.interrupt = interrupt
        self.terminated = False
        self.waits = 0

    def wait(self, timeout: float | None = None) -> int:
        self.waits += 1
        if self.interrupt and self.waits == 1:
            raise KeyboardInterrupt
        return 0

    def terminate(self) -> None:
        self.terminated = True


def test_the_ffplay_command_seeks_and_limits_the_sample() -> None:
    argv = procs.ffplay_argv(Path("speakers/ana.flac"), 41.0, 11.0)
    assert argv == [
        "ffplay",
        "-nodisp",
        "-autoexit",
        "-loglevel",
        "quiet",
        "-ss",
        "41.00",
        "-t",
        "11.00",
        str(Path("speakers/ana.flac")),
    ]


def test_play_runs_ffplay_and_reports_it(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[Any] = []

    def popen(argv: list[str], **kwargs: Any) -> _Process:
        started.append((argv, kwargs))
        return _Process()

    monkeypatch.setattr(procs, "which", lambda name: "/usr/bin/ffplay")
    monkeypatch.setattr(subprocess, "Popen", popen)
    assert procs.play(Path("a.flac"), 1.5, 3.0) is True
    argv, kwargs = started[0]
    assert argv[0] == "ffplay"
    assert kwargs["stdin"] == subprocess.DEVNULL


def test_without_ffplay_nothing_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(procs, "which", lambda name: None)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("must not start"))
    assert procs.play(Path("a.flac"), 0, 1) is False


def test_ctrl_c_stops_the_sample_but_not_saidby(monkeypatch: pytest.MonkeyPatch) -> None:
    process = _Process(interrupt=True)
    monkeypatch.setattr(procs, "which", lambda name: "/usr/bin/ffplay")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: process)
    assert procs.play(Path("a.flac"), 0, 1) is True
    assert process.terminated


def test_doctor_warns_about_a_missing_ffplay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnose, "which", lambda name: None)
    check = diagnose.check_ffplay()
    assert (check.name, check.status) == ("ffplay", "warn")
    assert check.hint
    monkeypatch.setattr(diagnose, "which", lambda name: "/usr/bin/ffplay")
    assert diagnose.check_ffplay().status == "ok"
