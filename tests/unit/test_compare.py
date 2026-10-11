# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from saidby.schema.diarization import Diarization, Turn, make_exclusive
from saidby.stages.compare import compare_diarizations


def _diar(*turns: tuple[float, float, str]) -> Diarization:
    items = [Turn(start=s, end=e, label=label) for s, e, label in turns]
    return Diarization(uri="u", turns=items, exclusive_turns=make_exclusive(items))


def test_identical_diarizations_agree_fully() -> None:
    a = _diar((0, 5, "A"), (6, 10, "B"))
    result = compare_diarizations(a, a, 12.0)
    assert result.agreement == 1.0
    assert result.spans == []


def test_label_names_do_not_matter() -> None:
    a = _diar((0, 5, "A"), (6, 10, "B"))
    b = _diar((0, 5, "X"), (6, 10, "Y"))
    assert compare_diarizations(a, b, 12.0).agreement == 1.0


def test_swapped_speaker_in_the_middle_is_reported() -> None:
    a = _diar((0, 4, "A"), (4, 8, "B"), (8, 12, "A"), (12, 16, "B"))
    b = _diar((0, 4, "A"), (4, 8, "B"), (8, 12, "B"), (12, 16, "B"))
    result = compare_diarizations(a, b, 16.0)
    assert result.agreement < 1.0
    assert len(result.spans) == 1
    start, end = result.spans[0]
    assert 8.0 <= start <= 8.5
    assert 11.5 <= end <= 12.0


def test_boundary_jitter_within_margin_is_ignored() -> None:
    a = _diar((0, 5.0, "A"), (5.0, 10, "B"))
    b = _diar((0, 5.2, "A"), (5.2, 10, "B"))
    result = compare_diarizations(a, b, 10.0)
    assert result.agreement == 1.0
    assert result.spans == []


def test_speech_versus_silence_counts_as_disagreement() -> None:
    a = _diar((0, 10, "A"))
    b = _diar((0, 4, "A"))
    result = compare_diarizations(a, b, 10.0)
    assert result.agreement < 0.6
    assert result.spans
    assert result.disagreement_s > 5.0


def test_short_differences_are_dropped_and_close_ones_merged() -> None:
    a = _diar((0, 20, "A"))
    b = _diar((0, 5, "A"), (5.1, 5.3, "B"), (5.3, 20, "A"))
    assert compare_diarizations(a, b, 20.0).spans == []
