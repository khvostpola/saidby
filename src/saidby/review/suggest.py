# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from typing import Any

from saidby.schema.correction import Correction
from saidby.schema.directory import Directory
from saidby.text.normalize import norm


@dataclass(frozen=True)
class Suggestion:
    kind: str
    target: str
    variant: str


def suggest_variants(directory: Directory, corrections: list[Correction]) -> list[Suggestion]:
    suggestions: list[Suggestion] = []
    seen: set[tuple[str, str]] = set()
    for c in corrections:
        if c.by != "review" or c.status != "accepted" or not c.from_ or not c.to:
            continue
        original, target = norm(c.from_), norm(c.to)
        for person in directory.people:
            known = {norm(x) for x in [person.name, *person.variants, *person.confusions]}
            if norm(person.name) == target and original not in known:
                _add(suggestions, seen, "person", person.id, c.from_)
        for term in directory.terms:
            known = {norm(x) for x in [term.term, *term.variants, *term.confusions]}
            if norm(term.term) == target and original not in known:
                _add(suggestions, seen, "term", term.term, c.from_)
    return suggestions


def _add(
    out: list[Suggestion], seen: set[tuple[str, str]], kind: str, target: str, variant: str
) -> None:
    key = (target, norm(variant))
    if key not in seen:
        seen.add(key)
        out.append(Suggestion(kind, target, variant.strip()))


def apply_suggestions(raw: Any, suggestions: list[Suggestion]) -> int:
    applied = 0
    for s in suggestions:
        entries = raw["people"] if s.kind == "person" else raw["terms"]
        key = "id" if s.kind == "person" else "term"
        for entry in entries:
            if entry[key] == s.target:
                variants = entry.get("variants")
                if variants is None:
                    entry["variants"] = [s.variant]
                else:
                    variants.append(s.variant)
                applied += 1
    return applied
