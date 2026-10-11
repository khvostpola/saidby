# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import pytest

from saidby.engines.llm.fake import FakeLlmClient
from saidby.ports.corrector import LlmTruncatedError
from saidby.schema.directory import Directory
from saidby.schema.transcript import Segment, Transcript, Word
from saidby.stages.correct import build_entries, build_system, llm_correct
from saidby.stages.glossary.prompts import template_for


def _directory() -> Directory:
    return Directory.model_validate(
        {
            "version": 1,
            "language": "es",
            "people": [{"id": "ana", "name": "Ana", "variants": ["Anna"], "confusions": ["Ani"]}],
            "terms": [
                {"term": "Acme", "variants": ["akme"], "context": "customer"},
                {"term": "Converge", "confusions": ["converse"]},
                {"term": "Max 5X", "variants": ["max x"]},
                {"term": "parce", "type": "dialect", "variants": ["parse"]},
            ],
        }
    )


def _transcript(text: str) -> Transcript:
    words = [
        Word(start=i * 0.5, end=i * 0.5 + 0.4, word=f" {w}") for i, w in enumerate(text.split())
    ]
    return Transcript(duration_s=60, segments=[Segment(start=0, end=30, words=words)])


def _run(text: str, changes: list[dict[str, Any]], **kwargs: Any) -> Any:
    client = FakeLlmClient(lambda system, user: {"changes": changes})
    return llm_correct(_transcript(text), _directory(), client, language="es", **kwargs), client


def _reasons(log: list[Any]) -> list[str | None]:
    return [c.reason for c in log]


def test_accepts_known_variant() -> None:
    (result, log, stats), _ = _run("hola akme equipo", [{"start": 1, "end": 1, "term": "Acme"}])
    assert [w.word for w in result.words()] == [" hola", " Acme", " equipo"]
    assert result.words()[1].source == "llm"
    assert (stats.accepted, stats.rejected) == (1, 0)
    assert log[0].status == "accepted"


def test_multiword_replacement_keeps_span_timing() -> None:
    (result, _, _), _ = _run("tengo max x hoy", [{"start": 1, "end": 2, "term": "Max 5X"}])
    words = result.words()
    assert [w.word for w in words] == [" tengo", " Max 5X", " hoy"]
    assert words[1].start == 0.5
    assert words[1].end == pytest.approx(1.4)


@pytest.mark.parametrize(
    ("text", "change", "reason"),
    [
        ("a b c", {"start": 5, "end": 6, "term": "Acme"}, "out_of_range"),
        ("a b c d e", {"start": 0, "end": 3, "term": "Acme"}, "span_too_long"),
        ("a b c", {"start": 0, "end": 0, "term": "Unknown"}, "term_not_allowed"),
        ("hola acme x", {"start": 1, "end": 1, "term": "Acme"}, "already_equal"),
        ("la cuenta de hoy", {"start": 0, "end": 2, "term": "Acme"}, "covers_extra_words"),
        ("hola zzzzz x", {"start": 1, "end": 1, "term": "Acme"}, "low_similarity"),
    ],
)
def test_guardrails_reject_with_reason(text: str, change: dict[str, Any], reason: str) -> None:
    (result, log, stats), _ = _run(text, [change])
    assert _reasons(log) == [reason]
    assert stats.accepted == 0
    assert [w.word.strip() for w in result.words()] == text.split()


def test_overlapping_changes_keep_the_first() -> None:
    (_, log, stats), _ = _run(
        "tengo max x hoy",
        [{"start": 1, "end": 2, "term": "Max 5X"}, {"start": 1, "end": 1, "term": "Max 5X"}],
    )
    assert stats.accepted == 1
    assert _reasons(log) == [None, "overlaps_change"]


def test_person_confusions_are_honoured() -> None:
    (result, _, stats), _ = _run("hablé con ani ayer", [{"start": 2, "end": 2, "term": "Ana"}])
    assert stats.accepted == 1
    assert result.words()[2].word == " Ana"


def test_truncated_response_skips_chunk_and_continues() -> None:
    calls = []

    def responder(system: str, user: str) -> dict[str, Any]:
        calls.append(user)
        if len(calls) == 1:
            raise LlmTruncatedError
        return {"changes": [{"start": 0, "end": 0, "term": "Acme"}]}

    client = FakeLlmClient(responder)
    text = " ".join(["akme"] * 4)
    result, log, stats = llm_correct(
        _transcript(text), _directory(), client, language="es", chunk_words=2
    )
    assert (stats.chunks, stats.truncated, stats.accepted) == (2, 1, 1)
    assert "truncated_response" in _reasons(log)
    assert [w.word.strip() for w in result.words()] == ["akme", "akme", "Acme", "akme"]


def test_chunking_numbers_words_per_chunk_and_never_changes_timestamps() -> None:
    (result, _, _), client = _run(
        "a b c d e", [{"start": 0, "end": 0, "term": "Acme"}], chunk_words=2, min_similarity=0.0
    )
    assert len(client.calls) == 3
    assert client.calls[1][1].endswith("0:c 1:d")
    original = _transcript("a b c d e")
    for before, after in zip(original.words(), result.words(), strict=True):
        assert before.start == after.start


def test_system_prompt_lists_directory_in_requested_language() -> None:
    entries = build_entries(_directory())
    assert all(e.term != "parce" for e in entries)
    es = build_system(template_for("es"), entries)
    en = build_system(template_for("en"), entries)
    assert "suele salir como: akme" in es
    assert "often comes out as: akme" in en
    assert "se confunde con la palabra real: converse" in es
    assert "Directorio:" in es
    assert "Directory:" in en
