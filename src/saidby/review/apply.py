# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from collections import Counter

from saidby.errors import UsageError
from saidby.review.queue import Item
from saidby.schema.correction import Correction
from saidby.schema.speakers import SpeakerEntry
from saidby.schema.transcript import Segment, Transcript, Word


def span_text(transcript: Transcript, item: Item) -> str:
    return "".join(w.word for w in transcript.words()[item.first : item.last + 1]).strip()


def resolve_speaker(speakers: list[SpeakerEntry], name: str) -> str:
    for entry in speakers:
        if name in (entry.label, entry.id) or name.casefold() == (entry.name or "").casefold():
            return entry.label
    known = ", ".join(s.label for s in speakers)
    raise UsageError(f"unknown speaker {name!r}; known: {known}")


def _rebuild(transcript: Transcript, first: int, last: int, new: list[Word]) -> Transcript:
    index = 0
    segments: list[Segment] = []
    inserted = False
    for segment in transcript.segments:
        words: list[Word] = []
        for word in segment.words:
            if first <= index <= last:
                if not inserted:
                    words.extend(new)
                    inserted = True
            else:
                words.append(word)
            index += 1
        if words:
            segments.append(
                Segment(
                    start=min(w.start for w in words), end=max(w.end for w in words), words=words
                )
            )
    return transcript.model_copy(update={"segments": segments})


def apply_text(
    transcript: Transcript, item: Item, text: str
) -> tuple[Transcript, Correction | None]:
    words = transcript.words()
    old = words[item.first : item.last + 1]
    tokens = text.split()
    before = "".join(w.word for w in old).strip()
    if not tokens or before.split() == tokens:
        return transcript, None
    speaker = Counter(w.speaker for w in old).most_common(1)[0][0]
    start, end = old[0].start, old[-1].end
    new: list[Word] = []
    if len(tokens) == len(old):
        for token, source in zip(tokens, old, strict=True):
            new.append(
                Word(
                    start=source.start,
                    end=source.end,
                    word=f" {token}",
                    p=None,
                    speaker=source.speaker,
                    source="review",
                )
            )
    else:
        step = (end - start) / len(tokens)
        for i, token in enumerate(tokens):
            new.append(
                Word(
                    start=round(start + i * step, 3),
                    end=round(start + (i + 1) * step, 3),
                    word=f" {token}",
                    p=None,
                    speaker=speaker,
                    source="review",
                )
            )
    log = Correction(
        t=round(start, 2),
        end=round(end, 2),
        from_=before,
        to=" ".join(tokens),
        by="review",
        status="accepted",
    )
    return _rebuild(transcript, item.first, item.last, new), log


def apply_speaker(transcript: Transcript, item: Item, label: str) -> Transcript:
    index = 0
    segments = []
    for segment in transcript.segments:
        words = []
        for current in segment.words:
            inside = item.first <= index <= item.last
            words.append(current.model_copy(update={"speaker": label}) if inside else current)
            index += 1
        segments.append(Segment(start=segment.start, end=segment.end, words=words))
    return transcript.model_copy(update={"segments": segments})
