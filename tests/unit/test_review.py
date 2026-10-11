# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from saidby.errors import UsageError
from saidby.formats.corrections_log import write_corrections
from saidby.review.apply import apply_speaker, apply_text, resolve_speaker, span_text
from saidby.review.queue import Item, build_queue, log_decision
from saidby.review.suggest import apply_suggestions, suggest_variants
from saidby.schema.correction import Correction
from saidby.schema.directory import Directory
from saidby.schema.manifest import AudioInfo, DeviceRecord, Manifest, SourceInfo
from saidby.schema.speakers import SpeakerEntry
from saidby.schema.transcript import Segment, Transcript, Word


def _transcript() -> Transcript:
    spec = [
        ("hola", 0.9, "A"),
        ("a", 0.95, "A"),
        ("todos", 0.9, "A"),
        ("vamos", 0.9, "B"),
        ("con", 0.2, "B"),
        ("akme", 0.3, "B"),
        ("hoy", 0.95, "B"),
        ("gracias", 0.9, "A"),
        ("por", 0.1, "A"),
        ("venir", 0.9, "A"),
    ]
    words = [
        Word(start=i * 1.0, end=i * 1.0 + 0.8, word=f" {w}", p=p, speaker=s)
        for i, (w, p, s) in enumerate(spec)
    ]
    return Transcript(
        duration_s=12,
        speakers=[SpeakerEntry(label="A", id="ana", name="Ana"), SpeakerEntry(label="B")],
        segments=[Segment(start=0, end=10, words=words)],
    )


def _manifest(spans: list[dict[str, float]] | None = None) -> Manifest:
    return Manifest(
        tool={"name": "saidby", "version": "0"},
        run_id="abc12345",
        status="ok",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        source=SourceInfo(path="x", sha256="0", size_bytes=1, duration_s=12),
        audio=AudioInfo(duration_s=12),
        device=DeviceRecord(requested="cpu", used="cpu"),
        compare={"disagreement_spans": spans} if spans is not None else None,
    )


def _directory() -> Directory:
    return Directory.model_validate(
        {
            "version": 1,
            "language": "es",
            "people": [{"id": "ana", "name": "Ana"}],
            "terms": [{"term": "Acme", "variants": ["akme"]}, {"term": "Converge"}],
        }
    )


def test_queue_orders_kinds_and_skips_overlaps(tmp_path: Path) -> None:
    write_corrections(
        tmp_path / "corrections.jsonl",
        [
            Correction(
                t=5.0, from_="akme", to="Acme", by="llm", status="rejected", reason="low_similarity"
            )
        ],
    )
    manifest = _manifest([{"start": 3.0, "end": 4.5}])
    queue = build_queue(tmp_path, _transcript(), manifest)
    assert [i.kind for i in queue] == ["diarization", "llm_rejected", "low_confidence"]
    assert (queue[0].first, queue[0].last) == (3, 4)
    assert queue[1].first == 5
    assert queue[2].first == 8
    assert queue[0].last == 4


def test_queue_skips_decided_and_filters_kinds(tmp_path: Path) -> None:
    transcript = _transcript()
    only_low = build_queue(tmp_path, transcript, _manifest(), kinds=("low_confidence",))
    assert len(only_low) == 2
    log_decision(tmp_path, only_low[0], "kept")
    log_decision(tmp_path, only_low[1], "skipped")
    remaining = build_queue(tmp_path, transcript, _manifest(), kinds=("low_confidence",))
    assert remaining == [only_low[1]]


def test_apply_text_same_length_keeps_timing() -> None:
    transcript = _transcript()
    item = Item("low_confidence", 4.0, 5.8, 4, 5)
    result, log = apply_text(transcript, item, "con Acme")
    assert log is not None
    assert (log.from_, log.to, log.by) == ("con akme", "con Acme", "review")
    words = result.words()
    assert [w.word for w in words[4:6]] == [" con", " Acme"]
    assert words[5].source == "review"
    assert words[5].start == 5.0
    assert words[5].speaker == "B"


def test_apply_text_different_length_spreads_over_span() -> None:
    transcript = _transcript()
    item = Item("low_confidence", 4.0, 5.8, 4, 5)
    result, _ = apply_text(transcript, item, "con la empresa Acme")
    words = result.words()
    assert len(words) == len(transcript.words()) + 2
    inside = words[4:8]
    assert [w.word.strip() for w in inside] == ["con", "la", "empresa", "Acme"]
    assert inside[0].start == 4.0
    assert inside[-1].end == pytest.approx(5.8)
    assert all(w.speaker == "B" for w in inside)


def test_apply_text_unchanged_returns_none() -> None:
    transcript = _transcript()
    item = Item("low_confidence", 4.0, 5.8, 4, 5)
    result, log = apply_text(transcript, item, "con akme")
    assert log is None
    assert result == transcript


def test_apply_speaker_and_resolution() -> None:
    transcript = _transcript()
    assert resolve_speaker(transcript.speakers, "ana") == "A"
    assert resolve_speaker(transcript.speakers, "ANA") == "A"
    with pytest.raises(UsageError):
        resolve_speaker(transcript.speakers, "nobody")
    result = apply_speaker(transcript, Item("diarization", 3.0, 4.8, 3, 4), "A")
    assert [w.speaker for w in result.words()[3:5]] == ["A", "A"]
    assert result.words()[5].speaker == "B"
    assert span_text(result, Item("x", 0, 1, 0, 1)) == "hola a"


def test_suggest_variants_only_for_unknown_forms() -> None:
    corrections = [
        Correction(t=1, from_="aknee", to="Acme", by="review", status="accepted"),
        Correction(t=2, from_="akme", to="Acme", by="review", status="accepted"),
        Correction(t=3, from_="converse", to="Converge", by="review", status="accepted"),
        Correction(t=4, from_="x", to="Unknown Thing", by="review", status="accepted"),
        Correction(t=5, from_="ani", to="Ana", by="review", status="accepted"),
        Correction(t=6, from_="aknee", to="Acme", by="review", status="accepted"),
    ]
    found = {(s.target, s.variant) for s in suggest_variants(_directory(), corrections)}
    assert found == {("Acme", "aknee"), ("Converge", "converse"), ("ana", "ani")}


def test_apply_suggestions_appends_variants() -> None:
    raw: dict[str, Any] = {
        "people": [{"id": "ana", "name": "Ana"}],
        "terms": [{"term": "Acme", "variants": ["akme"]}, {"term": "Converge"}],
    }
    corrections = [
        Correction(t=1, from_="aknee", to="Acme", by="review", status="accepted"),
        Correction(t=2, from_="converse", to="Converge", by="review", status="accepted"),
    ]
    count = apply_suggestions(raw, suggest_variants(_directory(), corrections))
    assert count == 2
    assert raw["terms"][0]["variants"] == ["akme", "aknee"]
    assert raw["terms"][1]["variants"] == ["converse"]
