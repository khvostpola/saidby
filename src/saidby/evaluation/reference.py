# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import difflib
import re
from dataclasses import dataclass

from saidby.errors import InputError
from saidby.i18n import _
from saidby.schema.transcript import Word
from saidby.text.normalize import norm

TURN_MARK = re.compile(r">>\s*(\S+)")
UNKNOWN_SPEAKERS = {"", "?"}


@dataclass(frozen=True)
class RefLine:
    start: float
    end: float
    speaker: str
    text: str


@dataclass(frozen=True)
class Reference:
    offset_s: float
    lines: list[RefLine]

    @property
    def window(self) -> tuple[float, float]:
        return (self.offset_s, self.offset_s + max((line.end for line in self.lines), default=0.0))

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines)

    @property
    def has_speakers(self) -> bool:
        return bool(self.lines) and all(line.speaker not in UNKNOWN_SPEAKERS for line in self.lines)


def clock(text: str) -> float:
    parts = text.strip().split(":")
    try:
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
    except ValueError as exc:
        raise InputError(_("bad time in reference: {text!r}").format(text=text)) from exc
    return seconds


def _words(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


def _split_turns(
    start: float, end: float, speaker: str, text: str, words: list[Word], offset: float
) -> list[RefLine]:
    parts = TURN_MARK.split(text)
    if len(parts) == 1:
        return [RefLine(start, end, speaker, text.strip())]
    pieces = [(speaker, parts[0]), *zip(parts[1::2], parts[2::2], strict=True)]
    span = [w for w in words if start - 0.5 <= w.start - offset < end + 0.5]
    hyp_tokens = [norm(w.word) for w in span]
    ref_tokens = [norm(t) for _label, chunk in pieces for t in _words(chunk)]
    matcher = difflib.SequenceMatcher(a=ref_tokens, b=hyp_tokens, autojunk=False)
    lines: list[RefLine] = []
    cursor, consumed = start, 0
    for i, (who, chunk) in enumerate(pieces):
        consumed += len(_words(chunk))
        if i == len(pieces) - 1:
            cut = end
        else:
            index = None
            for a0, b0, size in matcher.get_matching_blocks():
                if a0 <= consumed < a0 + size:
                    index = b0 + (consumed - a0)
                    break
                if a0 >= consumed:
                    index = b0
                    break
            cut = span[index].start - offset if index is not None and index < len(span) else cursor
        lines.append(RefLine(cursor, cut, who, chunk.strip()))
        cursor = cut
    return [line for line in lines if line.text]


def parse_reference(content: str, words: list[Word] | None = None) -> Reference:
    offset = 0.0
    rows = content.splitlines()
    for row in rows:
        if row.startswith("# offset_s:"):
            offset = float(row.split(":", 1)[1])
    lines: list[RefLine] = []
    for row in rows:
        if not row.strip() or row.startswith("#"):
            continue
        fields = [p.strip() for p in row.split("|", 2)]
        if len(fields) != 3 or "-" not in fields[0]:
            raise InputError(
                _("bad reference line (expected 'MM:SS-MM:SS | speaker | text'): {value!r}").format(
                    value=row[:40]
                )
            )
        first, last = fields[0].split("-", 1)
        lines.extend(
            _split_turns(clock(first), clock(last), fields[1], fields[2], words or [], offset)
        )
    if not lines:
        raise InputError(_("the reference has no lines"))
    return Reference(offset, lines)
