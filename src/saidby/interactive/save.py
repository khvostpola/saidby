# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from saidby.config.settings import find_project_config
from saidby.config.writer import DIRECTORY_STARTER, default_language, shorten_home
from saidby.formats.directory_edit import add_term
from saidby.formats.directory_yaml import load_directory, save_directory
from saidby.formats.yaml_io import save_yaml

DIRECTORY_NAME = "directory.yaml"


def config_target(explicit: Path | None) -> Path:
    return explicit or find_project_config() or Path.cwd() / "saidby.toml"


def path_for_config(path: Path, config_file: Path) -> str:
    try:
        return str(path.resolve().relative_to(config_file.resolve().parent))
    except ValueError:
        return shorten_home(path.resolve())


def new_terms(raw_terms: list[object], terms: list[str]) -> list[str]:
    known = {str(item["term"]).casefold() for item in raw_terms if isinstance(item, dict)}
    found: list[str] = []
    for term in terms:
        if term.casefold() not in known:
            known.add(term.casefold())
            found.append(term)
    return found


def add_terms_to_directory(path: Path, terms: list[str]) -> tuple[list[str], Path | None]:
    _model, raw = load_directory(path)
    found = new_terms(list(raw.get("terms") or []), terms)
    if not found:
        return [], None
    for term in found:
        add_term(raw, term=term)
    return found, save_directory(path, raw)


def create_directory_with_terms(path: Path, language: str | None, terms: list[str]) -> list[str]:
    path.write_text(
        DIRECTORY_STARTER.format(language=language or default_language()), encoding="utf-8"
    )
    _model, raw = load_directory(path)
    for term in terms:
        add_term(raw, term=term)
    save_yaml(path, raw, backup=False)
    return terms
