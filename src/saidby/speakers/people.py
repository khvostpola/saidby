# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from saidby.errors import UsageError
from saidby.formats.directory_edit import add_person
from saidby.formats.directory_yaml import load_directory, save_directory
from saidby.schema.directory import Directory, Person
from saidby.speakers.naming import ascii_slug, person_id_for


def find_person(directory: Directory, key: str) -> Person | None:
    wanted = key.strip().casefold()
    for person in directory.people:
        names = {person.id.casefold(), person.name.casefold()}
        names.update(alias.casefold() for alias in person.aliases)
        if wanted in names:
            return person
    return None


def add_person_to_file(path: Path, name: str) -> tuple[Person, Path | None]:
    if not ascii_slug(name):
        raise UsageError(
            f"cannot make an id from {name!r}; use saidby directory add-person with --id"
        )
    _, raw = load_directory(path)
    taken = [str(p["id"]) for p in raw.get("people") or []]
    person_id = person_id_for(name, taken)
    add_person(raw, person_id=person_id, name=name)
    backup = save_directory(path, raw)
    person = load_directory(path)[0].person(person_id)
    assert person is not None
    return person, backup
