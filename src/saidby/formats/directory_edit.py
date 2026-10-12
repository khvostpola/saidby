# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Sequence
from typing import Any

from saidby.errors import UsageError
from saidby.i18n import _


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
            raise UsageError(_("person {person_id!r} already exists").format(person_id=person_id))
        if str(person["name"]).casefold() == name.casefold():
            raise UsageError(
                _("{name!r} is already in the directory as {id!r}").format(
                    name=name, id=person["id"]
                )
            )
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
            raise UsageError(_("term {term!r} already exists").format(term=existing["term"]))
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
