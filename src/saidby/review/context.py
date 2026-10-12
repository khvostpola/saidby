# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from saidby.review.queue import Item
from saidby.schema.manifest import Manifest
from saidby.schema.speakers import SpeakerEntry
from saidby.schema.transcript import Transcript
from saidby.text.normalize import norm

CONTEXT_WORDS = 8
PLAY_PADDING_S = 0.5
MAX_OVERLAP = 3


@dataclass(frozen=True)
class Context:
    before: str
    span: str
    after: str
    more_before: bool = False
    more_after: bool = False


@dataclass(frozen=True)
class Overlap:
    lead: int = 0
    trail: int = 0

    def __bool__(self) -> bool:
        return bool(self.lead or self.trail)


def _join(words: list[str]) -> str:
    return "".join(words).strip()


def context_of(transcript: Transcript, item: Item, radius: int = CONTEXT_WORDS) -> Context:
    words = transcript.words()
    low = max(0, item.first - radius)
    high = item.last + 1 + radius
    return Context(
        before=_join([w.word for w in words[low : item.first]]),
        span=_join([w.word for w in words[item.first : item.last + 1]]),
        after=_join([w.word for w in words[item.last + 1 : high]]),
        more_before=low > 0,
        more_after=high < len(words),
    )


def _norms(tokens: list[str]) -> list[str]:
    return [norm(token) for token in tokens]


def find_overlap(transcript: Transcript, item: Item, text: str) -> Overlap:
    tokens = _norms(text.split())
    words = transcript.words()
    before = _norms([w.word for w in words[max(0, item.first - MAX_OVERLAP) : item.first]])
    after = _norms([w.word for w in words[item.last + 1 : item.last + 1 + MAX_OVERLAP]])
    lead = _longest(tokens, before, from_end=True)
    trail = _longest(tokens[lead:], after, from_end=False)
    return Overlap(lead, trail)


def _longest(tokens: list[str], neighbours: list[str], *, from_end: bool) -> int:
    for size in range(min(len(neighbours), len(tokens) - 1), 0, -1):
        head = tokens[:size] if from_end else tokens[len(tokens) - size :]
        near = neighbours[len(neighbours) - size :] if from_end else neighbours[:size]
        if head == near and all(head):
            return size
    return 0


def strip_overlap(text: str, overlap: Overlap) -> str:
    tokens = text.split()
    end = len(tokens) - overlap.trail
    return " ".join(tokens[overlap.lead : end])


def repeated_words(text: str, overlap: Overlap) -> str:
    tokens = text.split()
    return " ".join([*tokens[: overlap.lead], *tokens[len(tokens) - overlap.trail :]])


@dataclass(frozen=True)
class AudioSource:
    path: Path
    kind: str


def _majority_speaker(transcript: Transcript, item: Item) -> str | None:
    words = transcript.words()[item.first : item.last + 1]
    counts = Counter(w.speaker for w in words if w.speaker)
    return counts.most_common(1)[0][0] if counts else None


def _track_of(speakers: list[SpeakerEntry], label: str | None) -> str | None:
    for entry in speakers:
        if label in (entry.label, entry.id):
            return entry.track
    return None


def audio_source(
    out_dir: Path, transcript: Transcript, manifest: Manifest, item: Item
) -> AudioSource | None:
    kept = out_dir / ".work" / "audio.wav"
    if kept.is_file():
        return AudioSource(kept, "audio")
    track = _track_of(transcript.speakers, _majority_speaker(transcript, item))
    if track and (out_dir / track).is_file():
        return AudioSource(out_dir / track, "track")
    original = Path(manifest.source.path)
    if original.is_file():
        return AudioSource(original, "original")
    return None


def play_window(item: Item) -> tuple[float, float]:
    start = max(0.0, item.start - PLAY_PADDING_S)
    return start, item.end - start + PLAY_PADDING_S
