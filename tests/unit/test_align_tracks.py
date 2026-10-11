# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import numpy as np
import soundfile as sf

from saidby.schema.diarization import Diarization, Turn, make_exclusive
from saidby.schema.transcript import Segment, Transcript, Word
from saidby.stages.align import assign_speakers
from saidby.stages.tracks import render_track


def _diar(turns: list[Turn]) -> Diarization:
    return Diarization(uri="u", turns=turns, exclusive_turns=make_exclusive(turns))


def test_make_exclusive_gives_overlap_to_earlier_turn() -> None:
    turns = [Turn(start=0, end=3, label="A"), Turn(start=2, end=5, label="B")]
    assert make_exclusive(turns) == [
        Turn(start=0, end=3, label="A"),
        Turn(start=3, end=5, label="B"),
    ]


def test_align_by_overlap_and_nearest() -> None:
    diar = _diar([Turn(start=0, end=2, label="A"), Turn(start=3, end=5, label="B")])
    words = [
        Word(start=0.5, end=1.0, word=" a"),
        Word(start=3.5, end=4.0, word=" b"),
        Word(start=2.6, end=2.8, word=" gap"),
    ]
    transcript = Transcript(duration_s=5, segments=[Segment(start=0, end=4, words=words)])
    result = assign_speakers(transcript, diar)
    assert [w.speaker for w in result.words()] == ["A", "B", "B"]
    assert [s.label for s in result.speakers] == ["A", "B"]


def test_align_empty_diarization() -> None:
    transcript = Transcript(
        duration_s=1, segments=[Segment(start=0, end=1, words=[Word(start=0, end=1, word=" x")])]
    )
    result = assign_speakers(transcript, _diar([]))
    assert result.words()[0].speaker is None


def test_track_has_same_length_and_silence(tmp_path: Path) -> None:
    rate = 16000
    audio = (0.5 * np.sin(np.linspace(0, 400, rate * 5))).astype(np.float32)
    path = tmp_path / "t.flac"
    render_track(path, audio, [Turn(start=1.0, end=2.0, label="A")])
    data, got_rate = sf.read(path, dtype="float32")
    assert got_rate == rate
    assert len(data) == len(audio)
    assert np.max(np.abs(data[: rate - 10])) < 1e-4
    assert np.max(np.abs(data[2 * rate + 10 :])) < 1e-4
    assert np.max(np.abs(data[rate + 1000 : 2 * rate - 1000])) > 0.1
