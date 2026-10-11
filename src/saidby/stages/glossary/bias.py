# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable
from dataclasses import dataclass

from saidby.schema.directory import Directory

HOTWORDS_TOKEN_BUDGET = 223


@dataclass(frozen=True)
class Hotwords:
    text: str
    tokens: int
    truncated: bool


def approximate_tokens(text: str) -> int:
    return max(1, 2 * len(text.split())) if text.strip() else 0


def bias_terms(directory: Directory) -> list[str]:
    names = [p.name for p in directory.people]
    terms = [t.term for t in directory.terms if t.type != "dialect"]
    dialect = [t.term for t in directory.terms if t.type == "dialect"]
    return names + terms + dialect


def build_hotwords(
    directory: Directory,
    count_tokens: Callable[[str], int] = approximate_tokens,
    budget: int = HOTWORDS_TOKEN_BUDGET,
) -> Hotwords:
    chosen: list[str] = []
    truncated = False
    for item in bias_terms(directory):
        candidate = " ".join([*chosen, item])
        if count_tokens(candidate) > budget:
            truncated = True
            continue
        chosen.append(item)
    text = " ".join(chosen)
    return Hotwords(text=text, tokens=count_tokens(text) if text else 0, truncated=truncated)
