# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
import time

import pytest

from saidby.cli.progress import CLEAR, Progress
from saidby.cli.term import Terminal, detect


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
