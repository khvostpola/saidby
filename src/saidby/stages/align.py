# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import bisect
from collections import defaultdict

from saidby.schema.diarization import Diarization, Turn
from saidby.schema.speakers import SpeakerEntry
from saidby.schema.transcript import Segment, Transcript, Word


class _TurnIndex:
    def __init__(self, turns: list[Turn]) -> None:
        self.turns = sorted(turns, key=lambda t: t.start)
        self.starts = [t.start for t in self.turns]
        self.mids = [(t.start + t.end) / 2 for t in self.turns]

    def speaker_for(self, start: float, end: float) -> str | None:
        if not self.turns:
            return None
        overlap: dict[str, float] = defaultdict(float)
        first = max(0, bisect.bisect_right(self.starts, start) - 1)
        for turn in self.turns[first:]:
            if turn.start >= end:
                break
            inter = min(turn.end, end) - max(turn.start, start)
            if inter > 0:
                overlap[turn.label] += inter
        if overlap:
            return max(overlap, key=lambda label: overlap[label])
        mid = (start + end) / 2
        pos = bisect.bisect_left(self.mids, mid)
        near = [i for i in (pos - 1, pos) if 0 <= i < len(self.turns)]
        return self.turns[min(near, key=lambda i: abs(self.mids[i] - mid))].label


def assign_speakers(transcript: Transcript, diarization: Diarization) -> Transcript:
    index = _TurnIndex(diarization.exclusive_turns)
    segments = [
        Segment(
            start=seg.start,
            end=seg.end,
            words=[
                Word(**{**w.model_dump(), "speaker": index.speaker_for(w.start, w.end)})
                for w in seg.words
            ],
        )
        for seg in transcript.segments
    ]
    used = {w.speaker for s in segments for w in s.words if w.speaker}
    speakers = [
        SpeakerEntry(label=label, speech_s=round(diarization.speech_s(label), 3))
        for label in diarization.labels()
        if label in used or diarization.speech_s(label) > 0
    ]
    return transcript.model_copy(update={"segments": segments, "speakers": speakers})
