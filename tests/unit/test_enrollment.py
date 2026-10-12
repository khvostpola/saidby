# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import datetime as dt
from pathlib import Path

import pytest
import yaml

from saidby.errors import ConsentMissingError
from saidby.formats.consent_yaml import load_consents
from saidby.schema.directory import Person
from saidby.speakers.enrollment import ConsentInput, resolve_consents

ANA = Person(id="ana", name="Ana Gómez")
BEN = Person(id="ben", name="Ben Ruiz")


def test_each_person_gets_their_own_record(tmp_path: Path) -> None:
    path = tmp_path / "consent.yaml"
    provided = {
        "ana": ConsentInput("signed form", "Ana Gómez", dt.date(2026, 10, 1)),
        "ben": ConsentInput("verbal, recorded", "Carla (team lead)"),
    }
    resolved = resolve_consents([ANA, BEN], path, provided)
    assert (resolved["ana"].source, resolved["ana"].declared_by) == ("signed form", "Ana Gómez")
    assert resolved["ana"].date == dt.date(2026, 10, 1)
    assert resolved["ben"].declared_by == "Carla (team lead)"
    assert resolved["ben"].date == dt.date.today()
    saved = yaml.safe_load(path.read_text())
    assert [(r["person"], r["declared_by"]) for r in saved] == [
        ("ana", "Ana Gómez"),
        ("ben", "Carla (team lead)"),
    ]


def test_an_existing_record_is_reused_and_nothing_is_added(tmp_path: Path) -> None:
    path = tmp_path / "consent.yaml"
    resolve_consents([ANA], path, {"ana": ConsentInput("signed form", "Ana Gómez")})
    again = resolve_consents([ANA], path, {"ana": ConsentInput("other", "someone else")})
    assert again["ana"].source == "signed form"
    assert len(load_consents(path)[0]) == 1


def test_a_person_without_consent_stops_everything(tmp_path: Path) -> None:
    path = tmp_path / "consent.yaml"
    with pytest.raises(ConsentMissingError, match="no voiceprint consent recorded for ben"):
        resolve_consents([ANA, BEN], path, {"ana": ConsentInput("signed form", "Ana Gómez")})


def test_a_record_found_by_the_persons_name_counts(tmp_path: Path) -> None:
    path = tmp_path / "consent.yaml"
    path.write_text(
        yaml.safe_dump(
            [{"person": "Ana Gómez", "source": "form", "declared_by": "Ana", "date": "2026-10-01"}]
        )
    )
    assert resolve_consents([ANA], path, {})["ana"].source == "form"
