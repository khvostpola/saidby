# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from saidby.formats.rttm import format_rttm, parse_rttm
from saidby.formats.transcripts import blocks, render_txt, render_vtt, vtt_time
from saidby.schema.diarization import Turn
from saidby.schema.ids import slugify, unique_slugs
from saidby.schema.speakers import SpeakerEntry
from saidby.schema.transcript import Segment, Transcript, Word


def _transcript() -> Transcript:
    words = [
        Word(start=0.0, end=0.4, word=" hola", speaker="SPEAKER_00"),
        Word(start=0.5, end=0.9, word=" mundo", speaker="SPEAKER_00"),
        Word(start=1.2, end=1.6, word=" buenas", speaker="SPEAKER_01"),
    ]
    return Transcript(
        language="es",
        duration_s=2.0,
        speakers=[
            SpeakerEntry(label="SPEAKER_00", name="Ana"),
            SpeakerEntry(label="SPEAKER_01"),
        ],
        segments=[Segment(start=0.0, end=1.6, words=words)],
    )


def test_rttm_round_trip() -> None:
    turns = [Turn(start=1.0, end=2.5, label="A"), Turn(start=0.0, end=1.2, label="B")]
    parsed = parse_rttm(format_rttm("u", turns))
    assert sorted(parsed, key=lambda t: t.start) == sorted(turns, key=lambda t: t.start)


def test_txt_uses_names_and_blocks() -> None:
    assert (
        render_txt(_transcript()) == "[00:00:00] Ana: hola mundo\n[00:00:01] SPEAKER_01: buenas\n"
    )


def test_vtt_format() -> None:
    vtt = render_vtt(_transcript())
    assert vtt.startswith("WEBVTT\n\n00:00:00.000 --> 00:00:00.900\n<v Ana>hola mundo\n")
    assert "<v SPEAKER_01>buenas" in vtt
    assert vtt_time(3661.5) == "01:01:01.500"


def test_vtt_cues_split_long_blocks() -> None:
    words = [Word(start=i * 2.0, end=i * 2.0 + 0.5, word=f" w{i}", speaker="S") for i in range(10)]
    t = Transcript(duration_s=20, segments=[Segment(start=0, end=19, words=words)])
    assert all(b.end - b.start <= 8.0 for b in blocks(t, split_segments=True, max_s=8.0))


def test_transcript_json_round_trip() -> None:
    original = _transcript()
    restored = Transcript.model_validate_json(original.model_dump_json(by_alias=True))
    assert restored == original
    assert '"schema":"saidby.words/1"' in original.model_dump_json(by_alias=True)


def test_slugs() -> None:
    assert slugify("My Call (1).m4a") == "My_Call_1_.m4a".strip("._")
    assert slugify("???") == "recording"
    assert unique_slugs(["a", "a", "b", "a"]) == ["a", "a-2", "b", "a-3"]
