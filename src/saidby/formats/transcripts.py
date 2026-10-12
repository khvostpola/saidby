# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass

from saidby.schema.speakers import SpeakerEntry
from saidby.schema.transcript import Transcript, Word

MAX_CUE_S = 8.0
MIN_PAUSE_S = 0.3
CLAUSE_ENDINGS = (".", "?", "!", "…", ";", ":", ",")
CLOSING_MARKS = "\"'\u201d\u2019\u00bb)]"


@dataclass
class Block:
    speaker: str | None
    start: float
    end: float
    words: list[Word]

    @property
    def text(self) -> str:
        return "".join(w.word for w in self.words).strip()


def _ends_clause(word: Word) -> bool:
    return word.word.strip().rstrip(CLOSING_MARKS).endswith(CLAUSE_ENDINGS)


def _cut_after(block: Block) -> int:
    words = block.words
    middle = (block.start + block.end) / 2
    boundaries = range(len(words) - 1)

    def pause(i: int) -> float:
        return words[i + 1].start - words[i].end

    def off_centre(i: int) -> float:
        return abs(words[i].end - middle)

    pauses = [i for i in boundaries if pause(i) >= MIN_PAUSE_S]
    if pauses:
        return max(pauses, key=lambda i: (pause(i), -off_centre(i)))
    clauses = [i for i in boundaries if _ends_clause(words[i])]
    return min(clauses or boundaries, key=off_centre)


def _split_long(block: Block, max_s: float) -> list[Block]:
    if block.end - block.start <= max_s or len(block.words) < 2:
        return [block]
    cut = _cut_after(block)
    left = Block(block.speaker, block.start, block.words[cut].end, block.words[: cut + 1])
    right = Block(block.speaker, block.words[cut + 1].start, block.end, block.words[cut + 1 :])
    return _split_long(left, max_s) + _split_long(right, max_s)


def blocks(
    transcript: Transcript, *, split_segments: bool, max_s: float | None = None
) -> list[Block]:
    result: list[Block] = []
    for segment in transcript.segments:
        for index, word in enumerate(segment.words):
            starts_segment = split_segments and index == 0
            if result and not starts_segment and result[-1].speaker == word.speaker:
                result[-1].end = word.end
                result[-1].words.append(word)
            else:
                result.append(Block(word.speaker, word.start, word.end, [word]))
    if max_s is None:
        return result
    return [piece for block in result for piece in _split_long(block, max_s)]


def display_names(speakers: list[SpeakerEntry]) -> dict[str, str]:
    return {s.label: s.display for s in speakers}


def _clock(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def vtt_time(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def render_txt(transcript: Transcript) -> str:
    names = display_names(transcript.speakers)
    lines = []
    for block in blocks(transcript, split_segments=False):
        who = names.get(block.speaker or "", block.speaker or "UNKNOWN")
        lines.append(f"[{_clock(block.start)}] {who}: {block.text}")
    return "\n".join(lines) + "\n"


def render_vtt(transcript: Transcript) -> str:
    names = display_names(transcript.speakers)
    out = ["WEBVTT", ""]
    for block in blocks(transcript, split_segments=True, max_s=MAX_CUE_S):
        who = names.get(block.speaker or "", block.speaker or "UNKNOWN")
        out += [f"{vtt_time(block.start)} --> {vtt_time(block.end)}", f"<v {who}>{block.text}", ""]
    return "\n".join(out)
