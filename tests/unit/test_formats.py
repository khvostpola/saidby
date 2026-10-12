# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from saidby.formats.rttm import format_rttm, parse_rttm
from saidby.formats.transcripts import Block, blocks, render_txt, render_vtt, vtt_time
from saidby.schema.diarization import Turn
from saidby.schema.ids import slugify, unique_slugs
from saidby.schema.speakers import SpeakerEntry
from saidby.schema.transcript import Segment, Transcript, Word
from saidby.speakers.naming import track_path


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


def _run_of_words(
    count: int, *, marks: dict[int, str] | None = None, pauses: dict[int, float] | None = None
) -> list[Word]:
    marks, pauses = marks or {}, pauses or {}
    words: list[Word] = []
    clock = 0.0
    for i in range(count):
        clock += pauses.get(i, 0.0)
        words.append(
            Word(start=clock, end=clock + 0.5, word=f" w{i}{marks.get(i, '')}", speaker="S")
        )
        clock += 0.5
    return words


def _cues(words: list[Word]) -> list[Block]:
    end = words[-1].end
    t = Transcript(duration_s=end, segments=[Segment(start=0, end=end, words=words)])
    return blocks(t, split_segments=True, max_s=8.0)


def test_words_without_pauses_split_into_even_cues() -> None:
    assert [len(c.words) for c in _cues(_run_of_words(20))] == [10, 10]
    assert [len(c.words) for c in _cues(_run_of_words(60))] == [15, 15, 15, 15]


def test_words_without_pauses_break_after_punctuation_near_the_middle() -> None:
    cues = _cues(_run_of_words(20, marks={8: ",", 3: "."}))
    assert [len(c.words) for c in cues] == [9, 11]


def test_punctuation_is_found_behind_closing_quotes() -> None:
    cues = _cues(_run_of_words(20, marks={8: '."'}))
    assert [len(c.words) for c in cues] == [9, 11]


def test_a_real_pause_wins_over_punctuation_and_the_middle() -> None:
    cues = _cues(_run_of_words(20, marks={9: "."}, pauses={15: 0.6}))
    assert [len(c.words) for c in cues] == [15, 5]


def test_equal_pauses_cut_near_the_middle() -> None:
    cues = _cues(_run_of_words(10, pauses={i: 1.5 for i in range(1, 10)}))
    assert [len(c.words) for c in cues] == [3, 2, 3, 2]


def test_splitting_keeps_every_word_in_order_and_within_the_limit() -> None:
    words = _run_of_words(80, marks={11: ",", 40: "?"}, pauses={25: 0.4, 60: 1.2})
    cues = _cues(words)
    assert [w for c in cues for w in c.words] == words
    assert all(c.end - c.start <= 8.0 for c in cues)


def test_transcript_json_round_trip() -> None:
    original = _transcript()
    restored = Transcript.model_validate_json(original.model_dump_json(by_alias=True))
    assert restored == original
    assert '"schema":"saidby.words/1"' in original.model_dump_json(by_alias=True)


def test_slugs() -> None:
    assert slugify("My Call (1).m4a") == "My_Call_1_.m4a".strip("._")
    assert slugify("???") == "recording"
    assert unique_slugs(["a", "a", "b", "a"]) == ["a", "a-2", "b", "a-3"]


def test_slugs_dodge_reserved_windows_names_and_case_clashes() -> None:
    assert slugify("con") == "con_"
    assert slugify("NUL.m4a") == "NUL_.m4a"
    assert slugify("console") == "console"
    assert unique_slugs(["Call", "call", "CALL"]) == ["Call", "call-2", "CALL-3"]
    assert track_path(SpeakerEntry(label="SPEAKER_00", id="aux")) == "speakers/aux_.flac"
    assert track_path(SpeakerEntry(label="SPEAKER_00", id="ana")) == "speakers/ana.flac"
