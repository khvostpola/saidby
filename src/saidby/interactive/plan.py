# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
from dataclasses import dataclass
from pathlib import Path

from saidby.cli.paths import show_path, typed_path, unquote
from saidby.cli.ui import Ui
from saidby.config.settings import ENV_PREFIX, ORIGIN_ENV, ORIGIN_FLAG, Settings
from saidby.config.writer import check_language
from saidby.errors import SaidbyError
from saidby.formats.directory_set import load_directory_set
from saidby.i18n import _, ngettext

KEYS = {"", "t", "e", "q"}
LABEL_WIDTH = 10


@dataclass(frozen=True)
class RunPlan:
    settings: Settings
    added_terms: list[str]
    chosen: dict[str, str]


def split_terms(text: str, known: list[str]) -> list[str]:
    seen = {term.casefold() for term in known}
    found: list[str] = []
    for part in text.split(","):
        term = part.strip()
        if term and term.casefold() not in seen:
            seen.add(term.casefold())
            found.append(term)
    return found


class Planner:
    def __init__(self, ui: Ui, inputs: list[Path], settings: Settings) -> None:
        self.ui = ui
        self.inputs = inputs
        self.settings = settings
        self.added_terms: list[str] = []
        self.chosen: dict[str, str] = {}

    def _labels(self) -> dict[str, str]:
        return {
            "language": _("language"),
            "glossary": _("glossary"),
            "speakers": _("speakers"),
            "output": _("output"),
            "terms": _("terms"),
        }

    def _origin(self, key: str) -> str:
        if key in self.chosen:
            return _("chosen just now")
        origin = self.settings.origins.get(key)
        if origin is None:
            return _("default")
        if origin == ORIGIN_FLAG:
            return _("command line")
        if origin == ORIGIN_ENV:
            return f"{ENV_PREFIX}{key.upper()}"
        return show_path(Path(origin))

    def _glossary_value(self) -> tuple[str, bool]:
        files = self.settings.directory
        if not files:
            return _("none"), False
        names = ", ".join(show_path(p) for p in files)
        try:
            merged = load_directory_set(files).merged
        except (SaidbyError, ValueError) as exc:
            return f"{names} · {exc}", True
        people = ngettext("{n} person", "{n} people", len(merged.people))
        terms = ngettext("{n} term", "{n} terms", len(merged.terms))
        counts = f"{people.format(n=len(merged.people))} · {terms.format(n=len(merged.terms))}"
        return f"{names} · {counts}", False

    def _where(self, key: str) -> str:
        if key == "terms" and self.added_terms:
            return _("this recording")
        if key in self.chosen or key in self.settings.origins or key == "out":
            return self._origin(key)
        return ""

    def _show(self) -> None:
        paint = self.ui.term.paint
        labels = self._labels()
        settings = self.settings
        glossary, broken = self._glossary_value()
        terms = settings.terms
        rows = [
            ("glossary", labels["glossary"], glossary, "directory"),
            (
                "language",
                labels["language"],
                settings.language or _("detect it from the audio"),
                "language",
            ),
            (
                "speakers",
                labels["speakers"],
                str(settings.num_speakers) if settings.num_speakers else _("detect the number"),
                "num_speakers",
            ),
            ("output", labels["output"], show_path(settings.out) + os.sep, "out"),
            ("terms", labels["terms"], ", ".join(terms) if terms else _("none"), "terms"),
        ]
        count = len(self.inputs)
        title = ngettext("Ready to process {n} file", "Ready to process {n} files", count)
        self.ui.say()
        self.ui.say(paint(title.format(n=count), "bold"))
        for path in self.inputs[:4]:
            self.ui.say(paint(f"  {path.name}", "dim"))
        if count > 4:
            self.ui.say(paint("  " + _("and {n} more").format(n=count - 4), "dim"))
        self.ui.say()
        for name, label, value, key in rows:
            shown = paint(value, "red") if name == "glossary" and broken else value
            where = self._where(key)
            suffix = f"  {paint(where, 'dim')}" if where else ""
            self.ui.say(f"  {paint(label.ljust(LABEL_WIDTH), 'bold')}{shown}{suffix}")
        self.ui.say()
        keys = [
            ("Enter", _("start")),
            ("t", _("terms for this recording")),
            ("e", _("change something")),
            ("q", _("quit")),
        ]
        line = "   ".join(f"{paint(k, 'bold')} {paint(text, 'dim')}" for k, text in keys)
        self.ui.say(f"  {line}")

    def _language_check(self, text: str) -> str | None:
        if not text or text.lower() == "auto":
            return None
        try:
            check_language(text)
        except SaidbyError as exc:
            return str(exc)
        return None

    def ask_language_if_unset(self) -> None:
        if self.settings.language is not None:
            return
        answer = self.ui.ask(
            _("Language of the recording? (es, en, pt...)"),
            hint=_("[Enter: detect it]"),
            check=self._language_check,
        )
        self._set_language(answer)

    def _set_language(self, answer: str) -> None:
        if not answer or answer.lower() == "auto":
            self.settings = self.settings.model_copy(update={"language": None})
            self.chosen.pop("language", None)
            return
        language = check_language(answer)
        self.settings = self.settings.model_copy(update={"language": language})
        self.chosen["language"] = language

    def _add_terms(self) -> None:
        known = self.settings.terms
        text = self.ui.ask(_("Terms for this recording, separated by commas"))
        found = split_terms(text, known)
        self.added_terms.extend(found)
        if found:
            self.settings = self.settings.model_copy(
                update={"terms": [*self.settings.terms, *found]}
            )

    def _glossary_check(self, text: str) -> str | None:
        if not text:
            return None
        path = typed_path(text)
        if not path.is_file():
            return _("{path} is not a file").format(path=path)
        try:
            load_directory_set([path])
        except (SaidbyError, ValueError) as exc:
            return str(exc)
        return None

    def _speakers_check(self, text: str) -> str | None:
        if not text or (text.isdigit() and int(text) >= 1):
            return None
        return _("type a number of 1 or more, or Enter to detect it")

    def _change_glossary(self) -> None:
        answer = self.ui.ask(
            _("Directory file (replaces the current ones; Enter for none)"),
            check=self._glossary_check,
        )
        files = [typed_path(answer)] if answer else []
        self.settings = self.settings.model_copy(update={"directory": files})
        self.chosen["directory"] = str(files[0]) if files else ""

    def _change(self) -> None:
        labels = self._labels()
        names = list(labels.values())

        def known(text: str) -> str | None:
            return (
                None
                if not text or text.casefold() in {n.casefold() for n in names}
                else _("choose one of: {names}").format(names=", ".join(names))
            )

        answer = self.ui.ask(
            _("Change which one?"),
            hint=f"[{', '.join(names)}]",
            check=known,
            complete=lambda: names,
        )
        wanted = next((k for k, v in labels.items() if v.casefold() == answer.casefold()), None)
        if wanted == "language":
            self._set_language(
                self.ui.ask(
                    _("Language code (es, en, pt...)"),
                    hint=_("[Enter: detect it]"),
                    check=self._language_check,
                )
            )
        elif wanted == "glossary":
            self._change_glossary()
        elif wanted == "speakers":
            number = self.ui.ask(
                _("How many people speak?"),
                hint=_("[Enter: detect it]"),
                check=self._speakers_check,
            )
            self.settings = self.settings.model_copy(
                update={"num_speakers": int(number) if number else None}
            )
            if number:
                self.chosen["num_speakers"] = number
            else:
                self.chosen.pop("num_speakers", None)
        elif wanted == "output":
            folder = unquote(self.ui.ask(_("Output folder"), default=str(self.settings.out)))
            self.settings = self.settings.model_copy(update={"out": typed_path(folder)})
            self.chosen["out"] = folder
        elif wanted == "terms":
            self._add_terms()

    def run(self) -> RunPlan | None:
        self.ask_language_if_unset()

        def valid(text: str) -> str | None:
            return None if text.lower() in KEYS else _("type Enter, t, e or q")

        while True:
            self._show()
            key = self.ui.ask("", check=valid).lower()
            if key == "q":
                self.ui.say(f"  {self.ui.term.paint('→', 'yellow')} {_('nothing was run')}")
                return None
            if key == "t":
                self._add_terms()
            elif key == "e":
                self._change()
            else:
                return RunPlan(self.settings, self.added_terms, self.chosen)


def plan_run(ui: Ui, inputs: list[Path], settings: Settings) -> RunPlan | None:
    return Planner(ui, inputs, settings).run()
