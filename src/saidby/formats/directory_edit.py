# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Sequence
from typing import Any

from saidby.errors import UsageError


def add_person(
    raw: Any,
    *,
    person_id: str,
    name: str,
    aliases: Sequence[str] = (),
    variants: Sequence[str] = (),
    context: str | None = None,
) -> None:
    people = raw.setdefault("people", [])
    for person in people:
        if person["id"] == person_id:
            raise UsageError(f"person {person_id!r} already exists")
        if str(person["name"]).casefold() == name.casefold():
            raise UsageError(f"{name!r} is already in the directory as {person['id']!r}")
    entry: dict[str, Any] = {"id": person_id, "name": name}
    if aliases:
        entry["aliases"] = list(aliases)
    if variants:
        entry["variants"] = list(variants)
    if context:
        entry["context"] = context
    people.append(entry)


def add_term(
    raw: Any,
    *,
    term: str,
    variants: Sequence[str] = (),
    confusions: Sequence[str] = (),
    context: str | None = None,
    dialect: bool = False,
) -> None:
    terms = raw.setdefault("terms", [])
    for existing in terms:
        if str(existing["term"]).casefold() == term.casefold():
            raise UsageError(f"term {existing['term']!r} already exists")
    entry: dict[str, Any] = {"term": term}
    if dialect:
        entry["type"] = "dialect"
    if variants:
        entry["variants"] = list(variants)
    if confusions:
        entry["confusions"] = list(confusions)
    if context:
        entry["context"] = context
    terms.append(entry)
