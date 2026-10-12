# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import gettext
import os
import re
import sys
from pathlib import Path

DOMAIN = "saidby"
LOCALE_DIR = Path(__file__).parent / "locale"


class _State:
    translation: gettext.NullTranslations = gettext.NullTranslations()
    language = "en"


def _candidates(code: str) -> list[str]:
    base = re.split(r"[.@]", code, maxsplit=1)[0].replace("-", "_")
    if not base or base in {"C", "POSIX"}:
        return []
    primary = base.split("_", maxsplit=1)[0].lower()
    return list(dict.fromkeys([base, primary]))


def wanted_language(explicit: str | None = None) -> str:
    for value in (
        explicit,
        os.environ.get("SAIDBY_UI_LANG"),
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
        os.environ.get("LANG"),
    ):
        if value and _candidates(value):
            return value
    if sys.platform == "win32":
        from saidby.runtime import host

        system = host.system_language()
        if system:
            return system
    return "en"


def set_language(explicit: str | None = None, localedir: Path | None = None) -> str:
    wanted = wanted_language(explicit)
    for code in _candidates(wanted):
        try:
            _State.translation = gettext.translation(DOMAIN, str(localedir or LOCALE_DIR), [code])
        except FileNotFoundError:
            continue
        _State.language = code.split("_", maxsplit=1)[0].lower()
        return _State.language
    _State.translation = gettext.NullTranslations()
    _State.language = "en"
    return _State.language


def current_language() -> str:
    return _State.language


class Message(str):
    english: str

    def __new__(cls, text: str, english: str) -> "Message":
        instance = super().__new__(cls, text)
        instance.english = english
        return instance

    def format(self, *args: object, **kwargs: object) -> "Message":
        shown = str.format(self, *args, **kwargs)
        plain_args = tuple(_in_english(a) for a in args)
        plain_kwargs = {k: _in_english(v) for k, v in kwargs.items()}
        return Message(shown, self.english.format(*plain_args, **plain_kwargs))


def _in_english(value: object) -> object:
    return value.english if isinstance(value, Message) else value


def english_text(value: object) -> str:
    first = value.args[0] if isinstance(value, BaseException) and value.args else value
    return first.english if isinstance(first, Message) else str(value)


def _(message: str) -> str:
    return Message(_State.translation.gettext(message), message)


def N_(message: str) -> str:  # noqa: N802
    return message


def ngettext(singular: str, plural: str, count: int) -> str:
    english = singular if count == 1 else plural
    return Message(_State.translation.ngettext(singular, plural, count), english)
