# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.extract import extract_from_dir
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "saidby"
LOCALE = SOURCE / "locale"
TEMPLATE = LOCALE / "saidby.pot"
KEYWORDS = {"_": None, "N_": None, "ngettext": (1, 2)}
PROJECT = "saidby"
VERSION = "0"
STAMP = datetime(2026, 1, 1, tzinfo=UTC)
COPYRIGHT = "the saidby authors"
BUGS = "https://github.com/khvostpola/saidby/issues"


def extract() -> Catalog:
    catalog = Catalog(project=PROJECT, charset="utf-8", fuzzy=False)
    for filename, lineno, message, comments, _context in extract_from_dir(
        str(SOURCE),
        method_map=[("**.py", "python")],
        keywords=KEYWORDS,
        comment_tags=("TRANSLATORS:",),
    ):
        catalog.add(
            message,
            locations=[(f"src/saidby/{filename}", lineno)],
            auto_comments=comments,
        )
    return catalog


def write_template() -> Catalog:
    catalog = extract()
    with TEMPLATE.open("wb") as fh:
        write_po(fh, catalog, width=100, omit_header=True, sort_by_file=True)
    return catalog


def languages() -> list[str]:
    return sorted(p.parent.parent.name for p in LOCALE.glob("*/LC_MESSAGES/saidby.po"))


def po_path(language: str) -> Path:
    return LOCALE / language / "LC_MESSAGES" / "saidby.po"


def mo_path(language: str) -> Path:
    return po_path(language).with_suffix(".mo")


def update(language: str) -> None:
    template = write_template()
    path = po_path(language)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open("rb") as fh:
            current = read_po(fh, locale=language)
    else:
        current = Catalog(
            locale=language,
            project=PROJECT,
            version=VERSION,
            copyright_holder=COPYRIGHT,
            msgid_bugs_address=BUGS,
            last_translator=COPYRIGHT,
            language_team=COPYRIGHT,
            charset="utf-8",
        )
        current.header_comment = (
            f"# {language} translations for saidby.\n# Copyright (C) 2026 {COPYRIGHT}."
        )
    current.update(template, no_fuzzy_matching=True)
    current.fuzzy = False
    current.project = PROJECT
    current.version = VERSION
    current.creation_date = STAMP
    current.revision_date = STAMP
    with path.open("wb") as fh:
        write_po(fh, current, width=100, sort_by_file=True, include_previous=False)


def compile_catalog(language: str) -> None:
    with po_path(language).open("rb") as fh:
        catalog = read_po(fh, locale=language)
    with mo_path(language).open("wb") as fh:
        write_mo(fh, catalog, use_fuzzy=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maintain the saidby message catalogs.")
    parser.add_argument("action", choices=["extract", "update", "compile", "all"])
    parser.add_argument("languages", nargs="*", help="Languages (default: every catalog).")
    args = parser.parse_args(argv)
    if args.action == "extract":
        write_template()
        return 0
    chosen = args.languages or languages()
    if args.action in {"update", "all"}:
        for language in chosen:
            update(language)
    if args.action in {"compile", "all"}:
        for language in chosen:
            compile_catalog(language)
    return 0


if __name__ == "__main__":
    sys.exit(main())
