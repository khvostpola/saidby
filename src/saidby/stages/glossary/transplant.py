# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import difflib

from saidby.schema.correction import Correction
from saidby.schema.directory import Directory
from saidby.schema.transcript import Segment, Transcript, Word
from saidby.text.normalize import norm

MAX_LENGTH_DIFFERENCE = 2


def vocabulary(directory: Directory) -> set[str]:
    tokens: set[str] = set()
    for text in [t.term for t in directory.terms] + [p.name for p in directory.people]:
        tokens.update(norm(tok) for tok in text.split())
    tokens.discard("")
    return tokens


def _in_window(word: Word, windows: list[tuple[float, float]]) -> int | None:
    mid = (word.start + word.end) / 2
    for index, (start, end) in enumerate(windows):
        if start <= mid < end:
            return index
    return None


def _groups(
    plain: list[Word], biased: list[Word], windows: list[tuple[float, float]] | None
) -> list[tuple[list[int], list[Word]]]:
    if windows is None:
        return [(list(range(len(plain))), biased)]
    groups: list[tuple[list[int], list[Word]]] = [([], []) for _ in windows]
    for i, word in enumerate(plain):
        slot = _in_window(word, windows)
        if slot is not None:
            groups[slot][0].append(i)
    for word in biased:
        slot = _in_window(word, windows)
        if slot is not None:
            groups[slot][1].append(word)
    return groups


def transplant(
    plain: Transcript,
    biased: Transcript,
    vocab: set[str],
    windows: list[tuple[float, float]] | None = None,
) -> tuple[Transcript, list[Correction]]:
    pw = plain.words()
    inserts: dict[int, list[Word]] = {}
    drops: set[int] = set()
    log: list[Correction] = []
    for indices, bw in _groups(pw, biased.words(), windows):
        group = [pw[i] for i in indices]
        matcher = difflib.SequenceMatcher(
            a=[norm(w.word) for w in group], b=[norm(w.word) for w in bw], autojunk=False
        )
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op != "replace":
                continue
            incoming = bw[j1:j2]
            if not any(norm(w.word) in vocab for w in incoming):
                continue
            if abs((i2 - i1) - (j2 - j1)) > MAX_LENGTH_DIFFERENCE:
                continue
            first, last = indices[i1], indices[i2 - 1]
            start, end = pw[first].start, pw[last].end
            inserts[first] = [
                Word(start=start, end=end, word=w.word, p=w.p, speaker=None, source="bias")
                for w in incoming
            ]
            drops.update(indices[i1:i2])
            log.append(
                Correction(
                    t=round(start, 2),
                    end=round(end, 2),
                    from_="".join(w.word for w in group[i1:i2]).strip(),
                    to="".join(w.word for w in incoming).strip(),
                    by="bias",
                    status="accepted",
                )
            )
    index = 0
    segments = []
    for segment in plain.segments:
        words: list[Word] = []
        for word in segment.words:
            words.extend(inserts.get(index, []))
            if index not in drops:
                words.append(word)
            index += 1
        segments.append(Segment(start=segment.start, end=segment.end, words=words))
    log.sort(key=lambda c: c.t)
    return plain.model_copy(update={"segments": segments}), log
