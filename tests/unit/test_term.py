# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
import sys
import time

import pytest

from saidby.cli.progress import CLEAR, Progress
from saidby.cli.term import Terminal, detect, enable_vt, prepare_streams
from saidby.runtime import host


class Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_a_plain_stream_is_not_a_terminal() -> None:
    term = detect(io.StringIO(), {"TERM": "xterm", "COLORTERM": "truecolor"})
    assert (term.tty, term.color, term.truecolor) == (False, False, False)


@pytest.mark.parametrize("term_value", ["", "dumb"])
def test_dumb_terminals_get_no_features(term_value: str) -> None:
    term = detect(Tty(), {"TERM": term_value})
    assert (term.tty, term.color) == (False, False)


def test_color_and_truecolor_are_detected() -> None:
    plain = detect(Tty(), {"TERM": "xterm"})
    assert (plain.tty, plain.color, plain.truecolor) == (True, True, False)
    for value in ("truecolor", "24bit", "TrueColor"):
        assert detect(Tty(), {"TERM": "xterm", "COLORTERM": value}).truecolor


def test_no_color_turns_off_color_but_not_the_terminal() -> None:
    term = detect(Tty(), {"TERM": "xterm", "NO_COLOR": "1", "COLORTERM": "truecolor"})
    assert (term.tty, term.color, term.truecolor) == (True, False, False)
    assert detect(Tty(), {"TERM": "xterm", "NO_COLOR": ""}).color


def test_paint_wraps_only_when_color_is_on() -> None:
    on = Terminal(tty=True, color=True, truecolor=False, columns=80)
    off = Terminal(tty=True, color=False, truecolor=False, columns=80)
    assert on.paint("ok", "green", "bold") == "\x1b[32;1mok\x1b[0m"
    assert off.paint("ok", "green") == "ok"
    assert on.paint("", "green") == ""
    assert on.paint("ok") == "ok"


def test_fit_truncates_to_one_less_than_the_width() -> None:
    term = Terminal(tty=True, color=False, truecolor=False, columns=20)
    assert term.fit("short") == "short"
    assert term.fit("x" * 19) == "x" * 19
    assert term.fit("x" * 30) == "x" * 18 + "…"


def test_the_live_line_never_wraps_on_a_narrow_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "xterm")
    stream = Tty()
    narrow = Terminal(tty=True, color=False, truecolor=False, columns=30)
    progress = Progress("human", stream=stream, delay_s=0.01, interval_s=0.01, terminal=narrow)
    progress.stage_start(index=1, total=1, slug="call", stage="asr_bias")
    time.sleep(0.1)
    progress.stop()
    drawn = [part for part in stream.getvalue().split(CLEAR) if part]
    assert drawn
    assert all(len(part) <= 29 for part in drawn)
    assert drawn[0].endswith("…")


def test_windows_consoles_need_no_term_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host, "is_windows", lambda: True)
    term = detect(Tty(), {}, vt=lambda stream: True)
    assert (term.tty, term.color, term.truecolor) == (True, True, True)
    assert detect(io.StringIO(), {}, vt=lambda stream: True).tty is False
    assert detect(Tty(), {"TERM": "dumb"}, vt=lambda stream: True).tty is False
    no_color = detect(Tty(), {"NO_COLOR": "1"}, vt=lambda stream: True)
    assert (no_color.tty, no_color.color, no_color.truecolor) == (True, False, False)


def test_a_windows_console_without_ansi_support_gets_no_color(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host, "is_windows", lambda: True)
    term = detect(Tty(), {}, vt=lambda stream: False)
    assert (term.tty, term.color, term.truecolor) == (True, False, False)


def test_enabling_ansi_processing_never_raises() -> None:
    assert enable_vt(io.StringIO()) is (not host.is_windows())


def test_redirected_streams_become_utf8_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host, "is_windows", lambda: True)
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    err = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"s\xed\n"), encoding="cp1252"))
    prepare_streams()
    assert (out.encoding, out.errors) == ("utf-8", "replace")
    assert (err.encoding, err.errors) == ("utf-8", "replace")
    print("\u25b8 Ana G\u00f3mez")
    out.flush()
    assert out.buffer.getvalue() == "\u25b8 Ana G\u00f3mez\n".encode()
    assert sys.stdin.readline() == "s\ufffd\n"


def test_streams_are_left_alone_elsewhere(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host, "is_windows", lambda: False)
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", out)
    prepare_streams()
    assert out.encoding == "cp1252"
