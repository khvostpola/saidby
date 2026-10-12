# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import re

import pytest

from saidby.schema.directory import PERSON_ID_PATTERN
from saidby.speakers.naming import ascii_slug, person_id_for


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Ana", "ana"),
        ("Gómez", "gomez"),
        ("Ana María Gómez Peña", "ana-maria-gomez-pena"),
        ("  O'Brien & Sons  ", "o-brien-sons"),
        ("Carla Diaz", "carla-diaz"),
    ],
)
def test_ids_are_ascii_slugs(name: str, expected: str) -> None:
    assert person_id_for(name) == expected


def test_empty_or_non_latin_names_fall_back() -> None:
    assert ascii_slug("李雷") == ""
    assert person_id_for("李雷") == "speaker"
    assert person_id_for("") == "speaker"


def test_taken_ids_get_a_numeric_suffix() -> None:
    assert person_id_for("Ana", taken=["ana"]) == "ana-2"
    assert person_id_for("Ana", taken=["ana", "ana-2"]) == "ana-3"


def test_long_names_still_make_valid_ids() -> None:
    name = "Maria " * 30
    first = person_id_for(name)
    second = person_id_for(name, taken=[first])
    for person_id in (first, second):
        assert re.fullmatch(PERSON_ID_PATTERN, person_id)
