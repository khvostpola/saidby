# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
import sys

import pytest

from saidby.cli import ui
from saidby.cli.term import Terminal
from saidby.cli.ui import Ui, completions, ensure_terminal, parse_yes_no
from saidby.errors import UsageError
from saidby.i18n import set_language

PLAIN = Terminal(tty=True, color=False, truecolor=False, columns=80)
COLOR = Terminal(tty=True, color=True, truecolor=False, columns=80)


def _ui(answers: list[str], term: Terminal = PLAIN) -> tuple[Ui, list[str], io.StringIO]:
    prompts: list[str] = []
    feed = iter(answers)

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(feed)

    out = io.StringIO()
    return Ui(term, input_fn=fake_input, out=out), prompts, out


def test_an_answer_is_returned_trimmed() -> None:
    interface, prompts, _ = _ui(["  ana  "])
    assert interface.ask("Name or id?", hint="[keep SPEAKER_00]") == "ana"
    assert prompts == ["  Name or id? [keep SPEAKER_00] ▸ "]


def test_an_empty_answer_takes_the_default() -> None:
    interface, _, _ = _ui(["", "   "])
    assert interface.ask("Language?", default="es") == "es"
    assert interface.ask("Language?", default="es") == "es"
    assert _ui([""])[0].ask("Nothing?") == ""


def test_a_bad_answer_explains_and_asks_again() -> None:
    def check(text: str) -> str | None:
        return None if text.isdigit() else "type a number"

    interface, prompts, out = _ui(["many", "x", "2"])
    assert interface.ask("How many?", check=check) == "2"
    assert len(prompts) == 3
    assert out.getvalue() == "  ! type a number\n  ! type a number\n"


def test_the_default_goes_through_the_check_too() -> None:
    interface, prompts, out = _ui(["", "7"])
    assert (
        interface.ask("How many?", default="x", check=lambda t: None if t == "7" else "no") == "7"
    )
    assert out.getvalue() == "  ! no\n"
    assert len(prompts) == 2


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("y", True),
        ("YES", True),
        (" y ", True),
        ("n", False),
        ("No", False),
        ("s", None),
        ("sí", None),
        ("x", None),
        ("", None),
    ],
)
def test_yes_and_no_in_english(text: str, value: bool | None) -> None:
    assert parse_yes_no(text) is value


@pytest.mark.parametrize(
    ("text", "value"),
    [("s", True), (" Sí ", True), ("si", True), ("y", True), ("n", False), ("x", None)],
)
def test_spanish_adds_si_to_the_accepted_answers(text: str, value: bool | None) -> None:
    set_language("es")
    assert parse_yes_no(text) is value


def test_confirm_uses_the_default_and_shows_it_in_the_hint() -> None:
    interface, prompts, _ = _ui(["", ""])
    assert interface.confirm("Apply?", default=True) is True
    assert interface.confirm("Store voiceprints?", default=False) is False
    assert prompts[0].endswith("Apply? [Y/n] ▸ ")
    assert prompts[1].endswith("Store voiceprints? [y/N] ▸ ")


def test_confirm_insists_until_it_is_understood() -> None:
    interface, prompts, out = _ui(["maybe", "y"])
    assert interface.confirm("Apply?", default=False) is True
    assert "type y or n" in out.getvalue()
    assert len(prompts) == 2


def test_color_goes_on_the_hint_and_the_arrow() -> None:
    interface, prompts, _ = _ui([""], COLOR)
    interface.ask("Name?", hint="[x]")
    assert prompts[0] == "  Name? \x1b[2m[x]\x1b[0m \x1b[34m▸\x1b[0m "


def test_errors_are_red() -> None:
    interface, _, out = _ui([""], COLOR)
    interface.error("nope")
    assert out.getvalue() == "  \x1b[31m! nope\x1b[0m\n"


def test_ctrl_d_stops_like_ctrl_c() -> None:
    def hang_up(prompt: str) -> str:
        raise EOFError

    interface = Ui(PLAIN, input_fn=hang_up, out=io.StringIO())
    with pytest.raises(KeyboardInterrupt):
        interface.ask("Name?")


def test_say_prints_to_the_interface_stream() -> None:
    interface, _, out = _ui([])
    interface.say("hello")
    interface.say()
    assert out.getvalue() == "hello\n\n"


def test_completion_matches_ignoring_case_and_accents_of_the_prefix_only() -> None:
    options = ["ana", "Ana Gómez", "ben", "Ben Ruiz"]
    assert completions("a", options) == ["ana", "Ana Gómez"]
    assert completions("BEN R", options) == ["Ben Ruiz"]
    assert completions("", options) == options
    assert completions("z", options) == []


def test_the_options_for_completion_are_asked_each_time() -> None:
    taken = ["ana"]
    seen: list[list[str]] = []

    def options() -> list[str]:
        seen.append(list(taken))
        return ["ben"]

    interface, _, _ = _ui(["", ""])
    interface.ask("Name?", complete=options)
    taken.append("ben")
    interface.ask("Name?", complete=options)
    assert seen == [["ana"], ["ana", "ben"]]


def test_escape_codes_are_wrapped_for_readline_only_with_the_real_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert ui._for_readline("\x1b[2mx\x1b[0m") == "\x01\x1b[2m\x02x\x01\x1b[0m\x02"
    seen: list[str] = []

    def fake_input(prompt: str) -> str:
        seen.append(prompt)
        return "ok"

    monkeypatch.setattr("builtins.input", fake_input)
    real = Ui(COLOR, out=io.StringIO())
    assert real.ask("Name?", hint="[x]") == "ok"
    assert "\x01\x1b[2m\x02" in seen[0]


def test_prompts_carry_no_readline_markers_when_readline_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def fake_input(prompt: str) -> str:
        seen.append(prompt)
        return "ok"

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setitem(sys.modules, "readline", None)
    real = Ui(COLOR, out=io.StringIO())
    assert real.ask("Name?", hint="[x]") == "ok"
    assert "\x01" not in seen[0]
    assert "\x1b[2m" in seen[0]


def test_tab_completion_installs_and_restores_the_readline_state() -> None:
    import readline

    before = (readline.get_completer(), readline.get_completer_delims())
    with ui.tab_completion(["ana", "ben"]):
        completer = readline.get_completer()
        assert completer is not None
        assert [completer("a", 0), completer("a", 1)] == ["ana", None]
        assert readline.get_completer_delims() == "\n"
    assert (readline.get_completer(), readline.get_completer_delims()) == before


def test_without_a_terminal_interactive_mode_says_what_to_run_instead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ui, "interactive_streams", lambda: False)
    with pytest.raises(UsageError, match="needs a terminal; without one, use: saidby speakers map"):
        ensure_terminal("saidby speakers map OUT --set SPEAKER_00=NAME")
    monkeypatch.setattr(ui, "interactive_streams", lambda: True)
    ensure_terminal("anything")


def test_a_pipe_is_not_an_interactive_session(monkeypatch: pytest.MonkeyPatch) -> None:
    class Tty(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", Tty())
    monkeypatch.setattr(sys, "stdout", Tty())
    monkeypatch.setattr(sys, "stderr", Tty())
    assert ui.interactive_streams()
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    assert not ui.interactive_streams()
