# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import locale
import os
import re
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import tomlkit

from saidby.errors import UsageError
from saidby.formats.yaml_io import backup_path
from saidby.i18n import _
from saidby.runtime import host

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
    system = host.system_language()
    if system:
        return system
    code = "" if host.is_windows() else (locale.getlocale()[0] or "")
    return code[:2].lower() if re.match(r"[A-Za-z]{2}", code) else "en"


def check_language(language: str) -> str:
    if not LANGUAGE_PATTERN.fullmatch(language):
        raise UsageError(
            _("{language!r} is not a language code such as es, en or pt").format(language=language)
        )
    return language.lower()


def portable_path(path: Path) -> str:
    """A path to persist: forward slashes and `~/` on every system."""
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return path.as_posix()


def display_path(path: Path) -> str:
    """A path to show: the native separator and `~` for the home folder."""
    try:
        return "~" + os.sep + str(path.relative_to(Path.home()))
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


def _table(document: Any, name: str) -> Any:
    if name not in document:
        document.add(name, tomlkit.table())
    return document[name]


def update_config(
    path: Path,
    *,
    language: str | None = None,
    out: str | None = None,
    directory: Sequence[str] | None = None,
) -> Path | None:
    backup: Path | None = None
    if path.exists():
        document = tomlkit.parse(path.read_text(encoding="utf-8"))
        backup = backup_path(path)
        shutil.copy2(path, backup)
    else:
        document = tomlkit.document()
        document.add(tomlkit.comment("saidby settings. Command-line flags override them."))
        document.add(tomlkit.nl())
    if language is not None or out is not None:
        base = _table(document, "saidby")
        if language is not None:
            base["language"] = language
        if out is not None:
            base["out"] = out
    if directory is not None:
        _table(document, "glossary")["directory"] = list(directory)
    path.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")
    return backup
