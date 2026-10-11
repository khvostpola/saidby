# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import numpy as np

from saidby.engines.embed.fake import FakeEmbedder, vector_for
from saidby.formats.directory_yaml import encode_vector
from saidby.schema.directory import Directory
from saidby.stages.identify import Centroid, assign, pick_spans, usable_voiceprints


def _centroid(name: str) -> Centroid:
    return Centroid(vector_for(name), 10.0)


def test_pick_spans_prefers_longest_and_stops_at_target() -> None:
    spans = [(0.0, 2.0), (5.0, 9.0), (10.0, 11.0), (20.0, 26.0)]
    assert pick_spans(spans, 1.5, 8.0) == [(20.0, 26.0), (5.0, 9.0)]


def test_assign_matches_and_applies_threshold() -> None:
    enrolled = {"ana": vector_for("ana"), "ben": vector_for("ben")}
    result = assign(
        {"S0": _centroid("ana"), "S1": _centroid("stranger")},
        enrolled,
        {"S0": 30.0, "S1": 30.0},
        {"ana": "Ana", "ben": "Ben"},
    )
    assert result["S0"].person_id == "ana"
    assert result["S0"].name == "Ana"
    assert result["S1"].person_id is None
    assert result["S1"].score is not None


def test_assign_uses_each_person_once() -> None:
    enrolled = {"ana": vector_for("ana")}
    result = assign(
        {"S0": _centroid("ana"), "S1": _centroid("ana")},
        enrolled,
        {"S0": 30.0, "S1": 20.0},
        {"ana": "Ana"},
    )
    assert sorted(m.person_id or "" for m in result.values()) == ["", "ana"]


def test_assign_requires_minimum_speech() -> None:
    result = assign(
        {"S0": _centroid("ana")}, {"ana": vector_for("ana")}, {"S0": 2.0}, {"ana": "Ana"}
    )
    assert result["S0"].person_id is None


def test_assign_with_more_people_than_speakers() -> None:
    enrolled = {name: vector_for(name) for name in ("a", "b", "c", "d", "e", "f", "g", "h")}
    result = assign({"S0": _centroid("g")}, enrolled, {"S0": 9.0}, {n: n for n in enrolled})
    assert result["S0"].person_id == "g"


def _directory(model: str, revision: str, preprocessing: str) -> Directory:
    return Directory.model_validate(
        {
            "version": 1,
            "language": "es",
            "people": [
                {
                    "id": "ana",
                    "name": "Ana",
                    "voiceprint": {
                        "model": model,
                        "revision": revision,
                        "dim": 16,
                        "sample_rate": 16000,
                        "preprocessing": preprocessing,
                        "channel": "phone",
                        "seconds": 60,
                        "vector": encode_vector(vector_for("ana")),
                    },
                }
            ],
        }
    )


def test_usable_voiceprints_match_and_mismatch() -> None:
    embedder = FakeEmbedder()
    ok, warnings = usable_voiceprints(_directory("fake", "0" * 40, "fake;v1"), embedder)
    assert list(ok) == ["ana"]
    assert warnings == []
    skipped, warnings = usable_voiceprints(_directory("fake", "1" * 40, "fake;v1"), embedder)
    assert skipped == {}
    assert "enroll again" in warnings[0]
    assert np.allclose(ok["ana"], vector_for("ana"))
