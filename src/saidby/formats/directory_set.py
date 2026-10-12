# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from saidby.formats.consent_yaml import find_consent, load_consents
from saidby.formats.directory_yaml import load_directory
from saidby.schema.directory import Directory, Person, Term

CONSENT_FILE = "consent.yaml"


def consent_path(directory_file: Path) -> Path:
    return directory_file.with_name(CONSENT_FILE)


@dataclass(frozen=True)
class DirectoryFile:
    path: Path
    model: Directory
    raw: Any


@dataclass(frozen=True)
class DirectorySet:
    files: tuple[DirectoryFile, ...]
    merged: Directory
    voiceprint_files: dict[str, Path]
    skipped: tuple[str, ...]

    @property
    def paths(self) -> list[Path]:
        return [f.path for f in self.files]


def load_directory_set(paths: Iterable[Path]) -> DirectorySet:
    files: list[DirectoryFile] = []
    skipped: list[str] = []
    for path in dict.fromkeys(paths):
        model, raw = load_directory(path)
        records, _ = load_consents(consent_path(path))
        people: list[Person] = []
        for person in model.people:
            consented = find_consent(records, person.id, person.name) is not None
            if person.voiceprint and not consented:
                skipped.append(
                    f"voiceprint of {person.id} in {path} has no consent record in "
                    f"{consent_path(path)}; it was not used"
                )
                people.append(person.model_copy(update={"voiceprint": None}))
            else:
                people.append(person)
        files.append(DirectoryFile(path, model.model_copy(update={"people": people}), raw))
    if not files:
        raise ValueError("no directory files to load")
    merged, voiceprint_files = _merge(files)
    return DirectorySet(tuple(files), merged, voiceprint_files, tuple(skipped))


def _merge(files: list[DirectoryFile]) -> tuple[Directory, dict[str, Path]]:
    people: dict[str, Person] = {}
    terms: dict[str, Term] = {}
    voiceprint_files: dict[str, Path] = {}
    for file in files:
        for person in file.model.people:
            earlier = people.get(person.id)
            if person.voiceprint is not None:
                voiceprint_files[person.id] = file.path
                people[person.id] = person
            elif earlier is not None:
                people[person.id] = person.model_copy(update={"voiceprint": earlier.voiceprint})
            else:
                people[person.id] = person
        for term in file.model.terms:
            terms[term.term.casefold()] = term
    merged = Directory(
        version=1,
        language=files[-1].model.language,
        people=list(people.values()),
        terms=list(terms.values()),
    )
    return merged, voiceprint_files
