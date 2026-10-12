# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import re
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import TextIO

from saidby.cli.term import Terminal, detect
from saidby.errors import UsageError
from saidby.i18n import _

YES = {"y", "yes", "s", "si", "sí"}
NO = {"n", "no"}
ESCAPE = re.compile(r"(\x1b\[[0-9;]*m)")

Check = Callable[[str], str | None]
Options = Callable[[], Sequence[str]]


def interactive_streams() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty()


def ensure_terminal(equivalent: str) -> None:
    if not interactive_streams():
        message = _("interactive mode needs a terminal; without one, use: {command}")
        raise UsageError(message.format(command=equivalent))


def completions(prefix: str, options: Sequence[str]) -> list[str]:
    wanted = prefix.casefold()
    return [o for o in options if o.casefold().startswith(wanted)]


def parse_yes_no(text: str) -> bool | None:
    word = text.strip().casefold()
    if word in YES:
        return True
    if word in NO:
        return False
    return None


@contextmanager
def tab_completion(options: Sequence[str]) -> Iterator[None]:
    try:
        import readline
    except ImportError:
        yield
        return
    previous = readline.get_completer()
    delimiters = readline.get_completer_delims()

    def complete(text: str, state: int) -> str | None:
        found = completions(text, options)
        return found[state] if state < len(found) else None

    readline.set_completer_delims("\n")
    readline.set_completer(complete)
    readline.parse_and_bind("tab: complete")
    try:
        yield
    finally:
        readline.set_completer(previous)
        readline.set_completer_delims(delimiters)


def _readline_loaded() -> bool:
    try:
        import readline  # noqa: F401
    except ImportError:
        return False
    return True


def _for_readline(text: str) -> str:
    return ESCAPE.sub(lambda m: f"\x01{m.group(1)}\x02", text)


class Ui:
    def __init__(
        self,
        term: Terminal | None = None,
        *,
        input_fn: Callable[[str], str] | None = None,
        out: TextIO | None = None,
    ) -> None:
        self.out = out or sys.stderr
        self.term = term or detect(self.out)
        self._real_input = input_fn is None
        self._input = input_fn or input

    def say(self, text: str = "") -> None:
        print(text, file=self.out)

    def error(self, message: str) -> None:
        self.say(f"  {self.term.paint('! ' + message, 'red')}")

    def _read(self, prompt: str, options: Sequence[str]) -> str:
        shown = _for_readline(prompt) if self._real_input and _readline_loaded() else prompt
        try:
            if self._real_input and options:
                with tab_completion(options):
                    return self._input(shown)
            return self._input(shown)
        except EOFError:
            raise KeyboardInterrupt from None

    def ask(
        self,
        question: str,
        *,
        default: str = "",
        hint: str = "",
        check: Check | None = None,
        complete: Options | None = None,
    ) -> str:
        shown_hint = f" {self.term.paint(hint, 'dim')}" if hint else ""
        prompt = f"  {question}{shown_hint} {self.term.paint('▸', 'blue')} "
        while True:
            answer = self._read(prompt, list(complete()) if complete else []).strip() or default
            problem = check(answer) if check else None
            if problem is None:
                return answer
            self.error(problem)

    def confirm(self, question: str, *, default: bool) -> bool:
        hint = _("[Y/n]") if default else _("[y/N]")

        def check(text: str) -> str | None:
            return None if parse_yes_no(text) is not None else _("type y or n")

        answer = self.ask(question, default="y" if default else "n", hint=hint, check=check)
        return bool(parse_yes_no(answer))
