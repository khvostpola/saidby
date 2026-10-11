# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import difflib

from saidby.schema.directory import Directory
from saidby.schema.transcript import Transcript
from saidby.text.normalize import norm

MAX_NGRAM = 3
DEFAULT_PAD_S = 2.0
MERGE_GAP_S = 1.0
MIN_WINDOW_S = 3.0
SIMILARITY_BY_FORM_LENGTH = ((4, 0.85), (6, 0.75))
DEFAULT_SIMILARITY = 0.65
MIN_FORM_LENGTH = 3


def known_forms(directory: Directory) -> set[str]:
    forms: set[str] = set()
    for person in directory.people:
        forms.update(norm(x) for x in [person.name, *person.variants, *person.confusions])
    for term in directory.terms:
        if term.type == "dialect":
            continue
        forms.update(norm(x) for x in [term.term, *term.variants, *term.confusions])
    return {f for f in forms if len(f) >= MIN_FORM_LENGTH}


def similarity_needed(form: str) -> float:
    for max_length, needed in SIMILARITY_BY_FORM_LENGTH:
        if len(form) <= max_length:
            return needed
    return DEFAULT_SIMILARITY


def _close(candidate: str, form: str) -> bool:
    if candidate == form:
        return True
    if abs(len(candidate) - len(form)) > max(3, len(form) // 2):
        return False
    needed = similarity_needed(form)
    matcher = difflib.SequenceMatcher(a=candidate, b=form)
    return matcher.real_quick_ratio() >= needed and matcher.ratio() >= needed


def find_windows(
    transcript: Transcript,
    directory: Directory,
    *,
    pad_s: float = DEFAULT_PAD_S,
) -> list[tuple[float, float]]:
    forms = known_forms(directory)
    words = transcript.words()
    hits: list[tuple[float, float]] = []
    for i in range(len(words)):
        for n in range(1, MAX_NGRAM + 1):
            if i + n > len(words):
                break
            candidate = "".join(norm(w.word) for w in words[i : i + n])
            if len(candidate) < MIN_FORM_LENGTH:
                continue
            if any(_close(candidate, form) for form in forms):
                hits.append((words[i].start, words[i + n - 1].end))
                break
    duration = transcript.duration_s
    padded = [(max(0.0, s - pad_s), min(duration, e + pad_s)) for s, e in sorted(hits)]
    merged: list[tuple[float, float]] = []
    for start, end in padded:
        if merged and start - merged[-1][1] <= MERGE_GAP_S:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return [_widen(start, end, duration) for start, end in merged]


def _widen(start: float, end: float, duration: float) -> tuple[float, float]:
    if end - start >= MIN_WINDOW_S:
        return (round(start, 2), round(end, 2))
    missing = (MIN_WINDOW_S - (end - start)) / 2
    return (round(max(0.0, start - missing), 2), round(min(duration, end + missing), 2))


def total_seconds(windows: list[tuple[float, float]]) -> float:
    return round(sum(e - s for s, e in windows), 2)
