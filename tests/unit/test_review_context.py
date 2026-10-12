# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from datetime import UTC, datetime
from pathlib import Path

import pytest

from saidby.review.context import (
    Overlap,
    audio_source,
    context_of,
    find_overlap,
    play_window,
    repeated_words,
    strip_overlap,
)
from saidby.review.queue import Item
from saidby.schema.manifest import AudioInfo, DeviceRecord, Manifest, SourceInfo
from saidby.schema.speakers import SpeakerEntry
from saidby.schema.transcript import Segment, Transcript, Word

TEXT = ["hola", "a", "todos", "vamos", "con", "akme", "hoy", "gracias", "por", "venir"]


def _transcript(tracks: bool = True) -> Transcript:
    words = [
        Word(start=i * 1.0, end=i * 1.0 + 0.8, word=f" {w}", speaker="B" if 3 <= i <= 6 else "A")
        for i, w in enumerate(TEXT)
    ]
    return Transcript(
        duration_s=10,
        speakers=[
            SpeakerEntry(label="A", id="ana", track="speakers/ana.flac" if tracks else None),
            SpeakerEntry(label="B", track="speakers/B.flac" if tracks else None),
        ],
        segments=[Segment(start=0, end=10, words=words)],
    )


def _manifest(source: Path) -> Manifest:
    return Manifest(
        tool={"name": "saidby", "version": "0"},
        run_id="abc12345",
        status="ok",
        created_at=datetime.now(UTC),
        source=SourceInfo(path=str(source), sha256="0" * 64, size_bytes=1, duration_s=10),
        audio=AudioInfo(duration_s=10),
        device=DeviceRecord(requested="cpu", used="cpu"),
    )


ITEM = Item("low_confidence", 5.0, 5.8, 5, 5)


def test_context_is_the_words_around_the_span() -> None:
    context = context_of(_transcript(), ITEM, radius=3)
    assert (context.before, context.span, context.after) == (
        "todos vamos con",
        "akme",
        "hoy gracias por",
    )


def test_context_says_whether_there_is_more_on_each_side() -> None:
    middle = context_of(_transcript(), ITEM, radius=3)
    assert (middle.more_before, middle.more_after) == (True, True)
    whole = context_of(_transcript(), ITEM, radius=20)
    assert (whole.more_before, whole.more_after) == (False, False)


def test_context_is_cut_at_the_edges_of_the_transcript() -> None:
    first = context_of(_transcript(), Item("x", 0, 0.8, 0, 1), radius=5)
    assert (first.before, first.span) == ("", "hola a")
    last = context_of(_transcript(), Item("x", 9, 9.8, 9, 9), radius=5)
    assert (last.span, last.after) == ("venir", "")


def test_a_span_of_several_words_is_joined() -> None:
    context = context_of(_transcript(), Item("x", 3, 5.8, 3, 5), radius=2)
    assert context.span == "vamos con akme"
    assert context.before == "a todos"


def test_typing_the_neighbours_back_is_detected_on_both_sides() -> None:
    overlap = find_overlap(_transcript(), ITEM, "vamos con Acme hoy")
    assert overlap == Overlap(lead=2, trail=1)
    assert strip_overlap("vamos con Acme hoy", overlap) == "Acme"
    assert repeated_words("vamos con Acme hoy", overlap) == "vamos con hoy"


def test_matching_ignores_case_accents_and_punctuation() -> None:
    overlap = find_overlap(_transcript(), ITEM, "Con, Acme. HOY!")
    assert overlap == Overlap(lead=1, trail=1)
    assert strip_overlap("Con, Acme. HOY!", overlap) == "Acme."


def test_a_plain_replacement_has_no_overlap() -> None:
    assert not find_overlap(_transcript(), ITEM, "Acme")
    assert not find_overlap(_transcript(), ITEM, "Acme Corp")
    assert find_overlap(_transcript(), ITEM, "Acme Corp") == Overlap()


def test_at_least_one_word_is_always_left_to_replace_the_span() -> None:
    assert find_overlap(_transcript(), ITEM, "con") == Overlap()
    assert find_overlap(_transcript(), ITEM, "con hoy") == Overlap(lead=1, trail=0)
    assert strip_overlap("con hoy", Overlap(lead=1, trail=0)) == "hoy"


def test_only_the_three_nearest_words_count() -> None:
    far = find_overlap(_transcript(), ITEM, "a todos vamos con Acme")
    assert far == Overlap(lead=0, trail=0)
    near = find_overlap(_transcript(), ITEM, "todos vamos con Acme")
    assert near == Overlap(lead=3, trail=0)


def test_audio_comes_from_the_kept_work_file_first(tmp_path: Path) -> None:
    (tmp_path / ".work").mkdir()
    (tmp_path / ".work/audio.wav").write_bytes(b"x")
    (tmp_path / "speakers").mkdir()
    (tmp_path / "speakers/B.flac").write_bytes(b"x")
    source = audio_source(tmp_path, _transcript(), _manifest(tmp_path / "orig.m4a"), ITEM)
    assert source is not None
    assert (source.kind, source.path) == ("audio", tmp_path / ".work/audio.wav")


def test_then_from_the_track_of_the_voice_that_speaks_most_in_the_span(tmp_path: Path) -> None:
    (tmp_path / "speakers").mkdir()
    (tmp_path / "speakers/B.flac").write_bytes(b"x")
    (tmp_path / "speakers/ana.flac").write_bytes(b"x")
    source = audio_source(tmp_path, _transcript(), _manifest(tmp_path / "orig.m4a"), ITEM)
    assert source is not None
    assert (source.kind, source.path) == ("track", tmp_path / "speakers/B.flac")
    other = audio_source(
        tmp_path, _transcript(), _manifest(tmp_path / "orig.m4a"), Item("x", 0, 0.8, 0, 0)
    )
    assert other is not None
    assert other.path == tmp_path / "speakers/ana.flac"


def test_then_from_the_original_recording(tmp_path: Path) -> None:
    original = tmp_path / "orig.m4a"
    original.write_bytes(b"x")
    source = audio_source(tmp_path, _transcript(tracks=False), _manifest(original), ITEM)
    assert source is not None
    assert (source.kind, source.path) == ("original", original)


def test_without_any_audio_there_is_nothing_to_play(tmp_path: Path) -> None:
    assert audio_source(tmp_path, _transcript(), _manifest(tmp_path / "gone.m4a"), ITEM) is None


def test_the_play_window_adds_a_little_before_and_after() -> None:
    assert play_window(ITEM) == pytest.approx((4.5, 1.8))
    assert play_window(Item("x", 0.2, 1.0, 0, 0)) == pytest.approx((0.0, 1.5))
