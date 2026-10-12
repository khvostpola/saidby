# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import struct
import sys
from collections.abc import Iterator
from importlib import resources
from pathlib import Path

import pytest
from typer.testing import CliRunner

from saidby import i18n
from saidby.cli import app
from saidby.i18n import _, current_language, ngettext, set_language, wanted_language

runner = CliRunner()
PLURALS = "Plural-Forms: nplurals=2; plural=n != 1\n"


def _write_mo(path: Path, messages: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ids = sorted(messages)
    id_bytes = [i.encode() for i in ids]
    str_bytes = [messages[i].encode() for i in ids]
    count = len(ids)
    id_table_at = 28
    str_table_at = id_table_at + count * 8
    data_at = str_table_at + count * 8
    id_offsets, str_offsets, blob, cursor = [], [], b"", data_at
    for raw in id_bytes:
        id_offsets.append((len(raw), cursor))
        blob += raw + b"\0"
        cursor += len(raw) + 1
    for raw in str_bytes:
        str_offsets.append((len(raw), cursor))
        blob += raw + b"\0"
        cursor += len(raw) + 1
    header = struct.pack("Iiiiiii", 0x950412DE, 0, count, id_table_at, str_table_at, 0, 0)
    table = b"".join(struct.pack("ii", n, o) for n, o in id_offsets + str_offsets)
    path.write_bytes(header + table + blob)


@pytest.fixture
def catalogs(tmp_path: Path) -> Iterator[Path]:
    _write_mo(
        tmp_path / "es" / "LC_MESSAGES" / "saidby.mo",
        {
            "": "Content-Type: text/plain; charset=UTF-8\n" + PLURALS,
            "Files are ready": "Los archivos están listos",
            "one file\0%d files": "un archivo\0%d archivos",
        },
    )
    yield tmp_path
    set_language("en", tmp_path)


def test_without_a_catalog_messages_stay_in_english(tmp_path: Path) -> None:
    assert set_language("es", tmp_path) == "en"
    assert _("Files are ready") == "Files are ready"
    assert current_language() == "en"


def test_a_catalog_translates_and_unknown_messages_fall_back(catalogs: Path) -> None:
    assert set_language("es", catalogs) == "es"
    assert _("Files are ready") == "Los archivos están listos"
    assert _("Something never translated") == "Something never translated"
    assert ngettext("one file", "%d files", 1) == "un archivo"
    assert ngettext("one file", "%d files", 3) == "%d archivos"


def test_a_regional_code_uses_the_language_catalog(catalogs: Path) -> None:
    assert set_language("es_CO.UTF-8", catalogs) == "es"
    assert _("Files are ready") == "Los archivos están listos"


def test_english_and_unknown_languages_use_the_source_text(catalogs: Path) -> None:
    assert set_language("en", catalogs) == "en"
    assert _("Files are ready") == "Files are ready"
    assert set_language("fr", catalogs) == "en"


@pytest.mark.parametrize(
    ("env", "explicit", "expected"),
    [
        ({"LANG": "es_CO.UTF-8"}, None, "es_CO.UTF-8"),
        ({"LANG": "es_CO.UTF-8", "LC_ALL": "pt_BR"}, None, "pt_BR"),
        ({"LANG": "es", "SAIDBY_UI_LANG": "en"}, None, "en"),
        ({"SAIDBY_UI_LANG": "en"}, "pt", "pt"),
        ({"LANG": "C"}, None, "en"),
        ({"LANG": "C.UTF-8", "LC_ALL": "POSIX"}, None, "en"),
        ({}, None, "en"),
    ],
)
def test_language_is_chosen_flag_then_environment_then_system(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], explicit: str | None, expected: str
) -> None:
    for name in ("SAIDBY_UI_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert wanted_language(explicit) == expected


def test_ui_lang_is_a_root_option(catalogs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(i18n, "LOCALE_DIR", catalogs)
    result = runner.invoke(app, ["--ui-lang", "es", "directory", "--help"])
    assert result.exit_code == 0, result.output
    assert current_language() == "es"


def test_the_locale_folder_ships_with_the_package() -> None:
    folder = resources.files("saidby") / "locale"
    assert folder.is_dir()
    assert (folder / "README.md").is_file()
    assert "saidby" in sys.modules
