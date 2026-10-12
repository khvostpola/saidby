# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from saidby.schema.diarization import Turn
from saidby.speakers.samples import Sample, clean_samples, subtract, turn_counts, union


def _turns(*items: tuple[str, float, float]) -> list[Turn]:
    return [Turn(label=label, start=start, end=end) for label, start, end in items]


def test_union_merges_touching_and_overlapping_spans() -> None:
    assert union([(5, 6), (0, 2), (1, 3), (3, 4)]) == [(0, 4), (5, 6)]
    assert union([]) == []


def test_subtract_removes_the_other_speakers_time() -> None:
    assert subtract([(0, 10)], [(2, 3), (5, 6)]) == [(0, 2), (3, 5), (6, 10)]
    assert subtract([(0, 10)], [(0, 10)]) == []
    assert subtract([(0, 4), (6, 10)], [(3, 7)]) == [(0, 3), (7, 10)]
    assert subtract([(0, 4)], [(10, 12)]) == [(0, 4)]


def test_the_sample_is_the_longest_stretch_nobody_else_talks_over() -> None:
    turns = _turns(
        ("A", 0, 10),
        ("B", 3, 5),
        ("A", 20, 24),
        ("B", 30, 40),
    )
    samples = clean_samples(turns)
    assert samples["A"] == Sample("A", 5, 10, True)
    assert samples["B"] == Sample("B", 30, 40, True)


def test_a_long_stretch_is_cut_to_a_playable_length() -> None:
    samples = clean_samples(_turns(("A", 0, 60), ("B", 70, 71.8)))
    assert (samples["A"].start, samples["A"].end) == (0, 12.0)
    assert samples["B"].duration < 2


def test_pieces_shorter_than_the_minimum_are_not_clean() -> None:
    turns = _turns(("A", 0, 10), ("B", 1, 9.5))
    samples = clean_samples(turns)
    assert samples["A"].clean is False
    assert (samples["A"].start, samples["A"].end) == (0, 10)
    assert samples["B"] == Sample("B", 1, 9.5, False)


def test_a_voice_that_is_always_overlapped_still_gets_a_sample() -> None:
    samples = clean_samples(_turns(("A", 0, 10), ("B", 2, 8)))
    assert samples["B"].clean is False
    assert samples["B"].duration == 6


def test_turns_of_the_same_voice_that_touch_count_as_one_stretch() -> None:
    samples = clean_samples(_turns(("A", 0, 2), ("A", 2, 5), ("B", 10, 12)))
    assert samples["A"] == Sample("A", 0, 5, True)


def test_no_turns_no_samples() -> None:
    assert clean_samples([]) == {}


def test_turn_counts_per_label() -> None:
    turns = _turns(("A", 0, 1), ("B", 2, 3), ("A", 4, 5))
    assert turn_counts(turns) == {"A": 2, "B": 1}
