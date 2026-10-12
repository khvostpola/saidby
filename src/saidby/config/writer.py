# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import locale
import os
import re
from collections.abc import Sequence
from pathlib import Path

import tomlkit

from saidby.errors import UsageError

LANGUAGE_PATTERN = re.compile(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?")

DIRECTORY_STARTER = """version: 1
language: {language}
# People whose voices you want named. Add one with:
#   saidby directory add-person "Ana Gómez" --context accountant
# Names and terms the recognizer should spell right. Add one with:
#   saidby directory add-term Acme --variant akme
"""

CONSENT_STARTER = "# Voiceprint consent records: `saidby enroll` adds one per enrolled person.\n"


def default_language() -> str:
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name, "")
        match = re.match(r"([a-z]{2,3})(?:[_.@-]|$)", value)
        if match:
            return match.group(1)
    code = locale.getlocale()[0] or ""
    return code[:2].lower() if re.match(r"[A-Za-z]{2}", code) else "en"


def check_language(language: str) -> str:
    if not LANGUAGE_PATTERN.fullmatch(language):
        raise UsageError(f"{language!r} is not a language code such as es, en or pt")
    return language.lower()


def shorten_home(path: Path) -> str:
    home = Path.home()
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)


def render_config(*, language: str, directories: Sequence[str], out: str | None = None) -> str:
    document = tomlkit.document()
    document.add(tomlkit.comment("saidby settings. Command-line flags override them."))
    document.add(tomlkit.nl())
    base = tomlkit.table()
    base.add("language", language)
    if out is not None:
        base.add("out", out)
    document.add("saidby", base)
    glossary = tomlkit.table()
    glossary.add(tomlkit.comment("Far to near: a later file wins over an earlier one."))
    glossary.add("directory", list(directories))
    document.add("glossary", glossary)
    return tomlkit.dumps(document)
