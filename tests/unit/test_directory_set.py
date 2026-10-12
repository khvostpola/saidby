# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from saidby.formats.directory_set import consent_path, load_directory_set
from saidby.formats.directory_yaml import encode_vector


def _voiceprint(seed: int) -> dict[str, Any]:
    vector = np.random.default_rng(seed).standard_normal(8).astype(np.float32)
    return {
        "model": "fake",
        "revision": "0" * 40,
        "dim": 8,
        "sample_rate": 16000,
        "preprocessing": "fake;v1",
        "channel": "phone",
        "seconds": 60.0,
        "vector": encode_vector(vector),
    }


def _directory(
    folder: Path,
    *,
    people: list[dict[str, Any]] | None = None,
    terms: list[dict[str, Any]] | None = None,
    language: str = "es",
    consented: tuple[str, ...] = (),
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "directory.yaml"
    path.write_text(
        yaml.safe_dump(
            {"version": 1, "language": language, "people": people or [], "terms": terms or []}
        ),
        encoding="utf-8",
    )
    if consented:
        records = [
            {"person": p, "source": "form", "declared_by": p, "date": "2026-10-12"}
            for p in consented
        ]
        consent_path(path).write_text(yaml.safe_dump(records), encoding="utf-8")
    return path


def test_nearest_file_wins_but_keeps_a_farther_voiceprint(tmp_path: Path) -> None:
    far = _directory(
        tmp_path / "global",
        people=[{"id": "ana", "name": "Ana", "voiceprint": _voiceprint(1)}],
        terms=[{"term": "Acme", "variants": ["akme"]}, {"term": "Rappi"}],
        consented=("ana",),
    )
    near = _directory(
        tmp_path / "project",
        people=[
            {"id": "ana", "name": "Ana Gómez", "context": "accountant"},
            {"id": "ben", "name": "Ben"},
        ],
        terms=[{"term": "ACME", "variants": ["acne"]}],
        language="en",
    )
    result = load_directory_set([far, near])
    ana = result.merged.person("ana")
    assert ana is not None
    assert (ana.name, ana.context) == ("Ana Gómez", "accountant")
    assert ana.voiceprint is not None
    assert result.voiceprint_files == {"ana": far}
    assert [p.id for p in result.merged.people] == ["ana", "ben"]
    assert {t.term: t.variants for t in result.merged.terms} == {"ACME": ["acne"], "Rappi": []}
    assert result.merged.language == "en"
    assert result.paths == [far, near]
    assert result.skipped == ()


def test_a_voiceprint_needs_consent_in_its_own_file(tmp_path: Path) -> None:
    far = _directory(
        tmp_path / "global", people=[{"id": "ana", "name": "Ana", "voiceprint": _voiceprint(1)}]
    )
    near = _directory(tmp_path / "project", consented=("ana",))
    result = load_directory_set([far, near])
    ana = result.merged.person("ana")
    assert ana is not None
    assert ana.voiceprint is None
    assert result.voiceprint_files == {}
    assert len(result.skipped) == 1
    assert "ana" in result.skipped[0]
    assert str(far) in result.skipped[0]
    assert str(consent_path(far)) in result.skipped[0]


def test_consent_by_person_name_also_counts(tmp_path: Path) -> None:
    path = _directory(tmp_path, people=[{"id": "ana", "name": "Ana", "voiceprint": _voiceprint(1)}])
    consent_path(path).write_text(
        yaml.safe_dump(
            [{"person": "Ana", "source": "f", "declared_by": "Ana", "date": "2026-10-12"}]
        ),
        encoding="utf-8",
    )
    result = load_directory_set([path])
    assert result.merged.people[0].voiceprint is not None


def test_repeated_paths_load_once(tmp_path: Path) -> None:
    path = _directory(tmp_path, people=[{"id": "ana", "name": "Ana"}])
    assert load_directory_set([path, path]).paths == [path]


def test_nothing_to_load_is_an_error() -> None:
    with pytest.raises(ValueError, match="no directory files"):
        load_directory_set([])
