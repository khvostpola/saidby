# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from saidby.evaluation.reference import Reference
from saidby.formats.rttm import read_rttm
from saidby.formats.words_json import read_transcript
from saidby.schema.directory import Directory
from saidby.schema.transcript import Transcript, Word
from saidby.text.normalize import norm


def words_text(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def dialect_map(directory: Directory | None) -> dict[str, str]:
    if directory is None:
        return {}
    return {
        words_text(v): words_text(t.term)
        for t in directory.terms
        if t.type == "dialect"
        for v in t.variants
    }


def unify(text: str, mapping: dict[str, str]) -> str:
    return " ".join(mapping.get(tok, tok) for tok in words_text(text).split())


def window_words(transcript: Transcript, window: tuple[float, float]) -> list[Word]:
    return [w for w in transcript.words() if window[0] <= w.start < window[1]]


@dataclass(frozen=True)
class TermScore:
    in_reference: int
    occurrences: int
    correct_pct: float | None
    missed: dict[str, str]


def term_forms(directory: Directory) -> set[str]:
    terms = {t.term for t in directory.terms if t.type != "dialect"}
    for person in directory.people:
        terms.add(person.name)
        terms.update(person.aliases)
    return terms


def _count(term: str, text: str) -> int:
    pattern = rf"(?<!\w){re.escape(words_text(term))}(?!\w)"
    return len(re.findall(pattern, words_text(text)))


def score_terms(directory: Directory, reference_text: str, hypothesis_text: str) -> TermScore:
    per_term = {
        t: (_count(t, reference_text), _count(t, hypothesis_text))
        for t in sorted(term_forms(directory))
    }
    present = {t: ref for t, (ref, _) in per_term.items() if ref}
    hits = sum(min(ref, hyp) for ref, hyp in per_term.values())
    total = sum(present.values())
    return TermScore(
        in_reference=len(present),
        occurrences=total,
        correct_pct=round(100 * hits / total, 2) if total else None,
        missed={t: f"{hyp}/{ref}" for t, (ref, hyp) in per_term.items() if ref and hyp < ref},
    )


def score_wer(
    reference_text: str, hypothesis_text: str, mapping: dict[str, str]
) -> dict[str, float]:
    import jiwer

    return {
        "wer_pct": round(
            100 * jiwer.wer(words_text(reference_text), words_text(hypothesis_text)), 2
        ),
        "wer_dialect_unified_pct": round(
            100 * jiwer.wer(unify(reference_text, mapping), unify(hypothesis_text, mapping)), 2
        ),
    }


def score_diarization(
    reference: Reference, run_dir: Path, transcript: Transcript
) -> dict[str, Any]:
    from pyannote.core import Annotation, Segment
    from pyannote.metrics.diarization import DiarizationErrorRate

    window = reference.window
    truth = Annotation()
    for line in reference.lines:
        truth[Segment(reference.offset_s + line.start, reference.offset_s + line.end)] = (
            line.speaker
        )
    display = {s.file_id: s.display for s in transcript.speakers}
    hypothesis = Annotation()
    for turn in read_rttm(run_dir / "diarization.rttm"):
        start, end = max(turn.start, window[0]), min(turn.end, window[1])
        if end > start:
            hypothesis[Segment(start, end)] = display.get(turn.label, turn.label)
    detail = DiarizationErrorRate(collar=0.25, skip_overlap=False)(truth, hypothesis, detailed=True)
    total = detail["total"] or 1.0
    correct = spoken = 0.0
    for segment, _, who in truth.itertracks(yield_label=True):
        spoken += segment.duration
        for part, _, label in hypothesis.crop(segment).itertracks(yield_label=True):
            if norm(str(label)) == norm(str(who)):
                correct += part.duration
    return {
        "der_pct": round(100 * detail["diarization error rate"], 2),
        "confusion_pct": round(100 * detail["confusion"] / total, 2),
        "false_alarm_pct": round(100 * detail["false alarm"] / total, 2),
        "missed_pct": round(100 * detail["missed detection"] / total, 2),
        "speech_with_correct_name_pct": round(100 * correct / spoken, 2) if spoken else None,
    }


def load_run(run_dir: Path) -> Transcript:
    return read_transcript(run_dir / "transcript.words.json")
