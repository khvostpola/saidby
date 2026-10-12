# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass

from saidby.schema.diarization import Turn

Span = tuple[float, float]

MIN_CLEAN_S = 1.5
MAX_SAMPLE_S = 12.0


@dataclass(frozen=True)
class Sample:
    label: str
    start: float
    end: float
    clean: bool

    @property
    def duration(self) -> float:
        return self.end - self.start


def union(spans: list[Span]) -> list[Span]:
    merged: list[Span] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def subtract(spans: list[Span], others: list[Span]) -> list[Span]:
    left: list[Span] = []
    for start, end in spans:
        cursor = start
        for o_start, o_end in others:
            if o_end <= cursor:
                continue
            if o_start >= end:
                break
            if o_start > cursor:
                left.append((cursor, o_start))
            cursor = max(cursor, o_end)
        if cursor < end:
            left.append((cursor, end))
    return left


def _longest(spans: list[Span]) -> Span | None:
    return max(spans, key=lambda s: s[1] - s[0], default=None)


def clean_samples(
    turns: list[Turn], *, min_clean_s: float = MIN_CLEAN_S, max_s: float = MAX_SAMPLE_S
) -> dict[str, Sample]:
    by_label: dict[str, list[Span]] = {}
    for turn in turns:
        by_label.setdefault(turn.label, []).append((turn.start, turn.end))
    own = {label: union(spans) for label, spans in by_label.items()}
    samples: dict[str, Sample] = {}
    for label, spans in own.items():
        others = union([s for other, ss in own.items() if other != label for s in ss])
        alone = [s for s in subtract(spans, others) if s[1] - s[0] >= min_clean_s]
        best = _longest(alone)
        clean = best is not None
        if best is None:
            best = _longest(spans)
        if best is None:
            continue
        start, end = best
        samples[label] = Sample(label, start, min(end, start + max_s), clean)
    return samples


def turn_counts(turns: list[Turn]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for turn in turns:
        counts[turn.label] = counts.get(turn.label, 0) + 1
    return counts
