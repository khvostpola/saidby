# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from itertools import pairwise
from typing import Any

from saidby.schema.directory import Directory
from saidby.schema.transcript import Segment, Transcript, Word
from saidby.stages.glossary.bias import build_hotwords
from saidby.stages.glossary.dialect import apply_dialect, dialect_map
from saidby.stages.glossary.prompts import PROMPTS, template_for
from saidby.stages.glossary.transplant import transplant, vocabulary


def _directory(**extra: Any) -> Directory:
    return Directory.model_validate(
        {
            "version": 1,
            "language": "es",
            "people": [{"id": "ana", "name": "Ana"}],
            "terms": [
                {"term": "Acme", "variants": ["akme"]},
                {"term": "parce", "type": "dialect", "variants": ["parse"]},
                {"term": "Max 5X"},
            ],
            **extra,
        }
    )


def _transcript(text: str) -> Transcript:
    words = [
        Word(start=i * 0.5, end=i * 0.5 + 0.4, word=f" {w}", p=0.9)
        for i, w in enumerate(text.split())
    ]
    return Transcript(duration_s=10, segments=[Segment(start=0, end=5, words=words)])


def test_hotwords_order_names_terms_then_dialect() -> None:
    hot = build_hotwords(_directory())
    assert hot.text == "Ana Acme Max 5X parce"
    assert not hot.truncated


def test_hotwords_budget_truncates_and_reports() -> None:
    hot = build_hotwords(_directory(), count_tokens=lambda text: len(text.split()), budget=3)
    assert hot.truncated
    assert hot.tokens <= 3
    assert hot.text.startswith("Ana Acme")


def test_dialect_swap_keeps_leading_space_and_marks_source() -> None:
    result, log = apply_dialect(_transcript("vamos parse hoy"), dialect_map(_directory()))
    assert [w.word for w in result.words()] == [" vamos", " parce", " hoy"]
    assert result.words()[1].source == "dialect"
    assert [(c.from_, c.to, c.by) for c in log] == [("parse", "parce", "dialect")]


def test_transplant_takes_terms_from_biased_pass() -> None:
    plain = _transcript("hola akme equipo vamos")
    biased = _transcript("hola Acme equipo vamos")
    result, log = transplant(plain, biased, vocabulary(_directory()))
    assert [w.word for w in result.words()] == [" hola", " Acme", " equipo", " vamos"]
    assert result.words()[1].source == "bias"
    assert result.words()[1].start == plain.words()[1].start
    assert [(c.from_, c.to, c.by) for c in log] == [("akme", "Acme", "bias")]


def test_transplant_ignores_changes_without_directory_words() -> None:
    plain = _transcript("hola mundo equipo")
    biased = _transcript("hola planeta equipo")
    result, log = transplant(plain, biased, vocabulary(_directory()))
    assert [w.word for w in result.words()] == [" hola", " mundo", " equipo"]
    assert log == []


def test_transplant_rejects_large_length_changes() -> None:
    plain = _transcript("uno akme dos")
    biased = _transcript("uno Acme y mas palabras extra dos")
    _, log = transplant(plain, biased, vocabulary(_directory()))
    assert log == []


def test_prompts_exist_for_es_en_pt_and_fall_back_to_english() -> None:
    assert {"es", "en", "pt"} <= set(PROMPTS)
    assert template_for("es-CO") is PROMPTS["es"]
    assert template_for("pt") is PROMPTS["pt"]
    assert template_for("fr") is PROMPTS["en"]
    assert template_for(None) is PROMPTS["en"]


def test_find_windows_around_near_matches_and_merges() -> None:
    from saidby.stages.glossary.windows import find_windows

    words = [
        Word(start=i * 1.0, end=i * 1.0 + 0.8, word=f" {w}")
        for i, w in enumerate(
            [
                "hola",
                "equipo",
                "hoy",
                "akme",
                "con",
                "converse",
                "y",
                "mas",
                "cosas",
                "sin",
                "relacion",
                "alguna",
                "para",
                "nadie",
                "ana",
            ]
        )
    ]
    transcript = Transcript(duration_s=40, segments=[Segment(start=0, end=14, words=words)])
    windows = find_windows(transcript, _directory(), pad_s=1.0)
    assert len(windows) >= 2
    assert windows[0][0] <= 3.0 <= windows[0][1]
    for (_, end), (start, _) in pairwise(windows):
        assert start > end
    assert all(e - s >= 3.0 for s, e in windows)


def test_find_windows_ignores_unrelated_words() -> None:
    from saidby.stages.glossary.windows import find_windows

    transcript = _transcript("buenos dias a todos vamos a empezar la reunion")
    assert find_windows(transcript, _directory()) == []


def test_windowed_transplant_only_changes_inside_windows() -> None:
    plain = _transcript("hola akme vamos akme otra vez")
    biased = Transcript(
        duration_s=10,
        segments=[Segment(start=0, end=5, words=plain.words()[:3])],
    )
    biased.segments[0].words[1] = Word(start=0.5, end=0.9, word=" Acme", p=0.9)
    result, log = transplant(plain, biased, vocabulary(_directory()), windows=[(0.0, 1.4)])
    assert [w.word.strip() for w in result.words()] == [
        "hola",
        "Acme",
        "vamos",
        "akme",
        "otra",
        "vez",
    ]
    assert len(log) == 1
