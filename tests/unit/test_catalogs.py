# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest
from babel.messages.mofile import read_mo
from babel.messages.pofile import read_po

from saidby.cli.banner import LABEL_WIDTH, WORD_WIDTH

ROOT = Path(__file__).resolve().parents[2]


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("i18n_tool", ROOT / "tools" / "i18n.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = _load_tool()
LANGUAGES = tool.languages()


def _ids(message_id: str | tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return (message_id,) if isinstance(message_id, str) else tuple(message_id)


def _key(message_id: str | tuple[str, ...] | list[str]) -> str:
    return _ids(message_id)[0]


def _strings(string: str | tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    return _ids(string or "")


def _po(language: str) -> dict[str, tuple[str, ...]]:
    with tool.po_path(language).open("rb") as fh:
        catalog = read_po(fh, locale=language)
    return {_key(m.id): _strings(m.string) for m in catalog if m.id}


def _source_ids() -> set[str]:
    return {_key(m.id) for m in tool.extract() if m.id}


def _fields(text: str) -> list[str]:
    return sorted(re.findall(r"\{[^{}]*\}", text))


def test_there_is_a_spanish_catalog() -> None:
    assert "es" in LANGUAGES


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_message_in_the_source_is_translated(language: str) -> None:
    translated = _po(language)
    missing = sorted(i for i in _source_ids() if not all(translated.get(i, ("",))))
    assert not missing, (
        f"{len(missing)} untranslated message(s) in {language}; run "
        f"`uv run python tools/i18n.py update {language}`, translate them and run "
        f"`uv run python tools/i18n.py compile`: {missing[:5]}"
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_catalog_has_nothing_the_source_no_longer_uses(language: str) -> None:
    unused = sorted(set(_po(language)) - _source_ids())
    assert not unused, f"obsolete messages in {language}; run tools/i18n.py update: {unused[:5]}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_compiled_catalog_matches_the_po_file(language: str) -> None:
    with tool.mo_path(language).open("rb") as fh:
        compiled = read_mo(fh)
    from_mo = {_key(m.id): _strings(m.string) for m in compiled if m.id}
    assert from_mo == _po(language), "stale .mo; run `uv run python tools/i18n.py compile`"


@pytest.mark.parametrize("language", LANGUAGES)
def test_placeholders_survive_translation(language: str) -> None:
    with tool.po_path(language).open("rb") as fh:
        catalog = read_po(fh, locale=language)
    for message in catalog:
        if not message.id:
            continue
        sources = _ids(message.id)
        for translated in _strings(message.string):
            assert _fields(translated) == _fields(sources[0]) or _fields(translated) == _fields(
                sources[-1]
            ), f"{message.id!r} -> {translated!r}"


def test_the_template_lists_exactly_what_the_source_asks_for() -> None:
    with tool.TEMPLATE.open("rb") as fh:
        template = read_po(fh)
    assert {_key(m.id) for m in template if m.id} == _source_ids(), (
        "stale template; run `uv run python tools/i18n.py update`"
    )


def test_translated_banner_text_fits_the_cassette() -> None:
    spanish = _po("es")
    assert len(spanish["Diarized transcription · offline"][0]) <= WORD_WIDTH
    for label in ("Models", "Device", "Glossary", "Config"):
        assert len(spanish[label][0]) < LABEL_WIDTH, label
