# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from saidby.schema.correction import Correction
from saidby.schema.directory import Directory
from saidby.schema.transcript import Segment, Transcript
from saidby.text.normalize import norm


def dialect_map(directory: Directory) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for term in directory.terms:
        if term.type == "dialect":
            for variant in term.variants:
                mapping[norm(variant)] = term.term
    return mapping


def apply_dialect(
    transcript: Transcript, mapping: dict[str, str]
) -> tuple[Transcript, list[Correction]]:
    log: list[Correction] = []
    segments = []
    for segment in transcript.segments:
        words = []
        for original in segment.words:
            word = original
            key = norm(word.word)
            target = mapping.get(key)
            if target is not None and key != norm(target):
                lead = word.word[: len(word.word) - len(word.word.lstrip())]
                log.append(
                    Correction(
                        t=round(word.start, 2),
                        end=round(word.end, 2),
                        from_=word.word.strip(),
                        to=target,
                        by="dialect",
                        status="accepted",
                    )
                )
                word = word.model_copy(update={"word": lead + target, "source": "dialect"})
            words.append(word)
        segments.append(Segment(start=segment.start, end=segment.end, words=words))
    return transcript.model_copy(update={"segments": segments}), log
