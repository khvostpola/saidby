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


def transplant(
    plain: Transcript, biased: Transcript, vocab: set[str]
) -> tuple[Transcript, list[Correction]]:
    pw = plain.words()
    bw = biased.words()
    matcher = difflib.SequenceMatcher(
        a=[norm(w.word) for w in pw], b=[norm(w.word) for w in bw], autojunk=False
    )
    inserts: dict[int, list[Word]] = {}
    drops: set[int] = set()
    log: list[Correction] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op != "replace":
            continue
        incoming = bw[j1:j2]
        if not any(norm(w.word) in vocab for w in incoming):
            continue
        if abs((i2 - i1) - (j2 - j1)) > MAX_LENGTH_DIFFERENCE:
            continue
        start, end = pw[i1].start, pw[i2 - 1].end
        inserts[i1] = [
            Word(start=start, end=end, word=w.word, p=w.p, speaker=None, source="bias")
            for w in incoming
        ]
        drops.update(range(i1, i2))
        log.append(
            Correction(
                t=round(start, 2),
                end=round(end, 2),
                from_="".join(w.word for w in pw[i1:i2]).strip(),
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
    return plain.model_copy(update={"segments": segments}), log
