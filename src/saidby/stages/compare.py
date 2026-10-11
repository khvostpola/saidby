# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from math import ceil

import numpy as np
from scipy.optimize import linear_sum_assignment

from saidby.schema.diarization import Diarization, Turn

FRAME_S = 0.01
DEFAULT_MARGIN_S = 0.25
MIN_SPAN_S = 0.3
MERGE_GAP_S = 0.5


@dataclass(frozen=True)
class CompareResult:
    margin_s: float
    agreement: float
    disagreement_s: float
    spans: list[tuple[float, float]]


def _labels_per_frame(turns: list[Turn], frames: int, names: dict[str, int]) -> np.ndarray:
    out = np.full(frames, -1, dtype=np.int32)
    for turn in turns:
        lo = max(0, int(turn.start / FRAME_S))
        hi = min(frames, ceil(turn.end / FRAME_S))
        out[lo:hi] = names[turn.label]
    return out


def _boundary_mask(turns: list[Turn], frames: int, margin_s: float) -> np.ndarray:
    mask = np.zeros(frames, dtype=bool)
    reach = round(margin_s / FRAME_S)
    for turn in turns:
        for edge in (turn.start, turn.end):
            center = round(edge / FRAME_S)
            mask[max(0, center - reach) : min(frames, center + reach + 1)] = True
    return mask


def _map_labels(a: np.ndarray, b: np.ndarray, count_a: int, count_b: int) -> dict[int, int]:
    both = (a >= 0) & (b >= 0)
    overlap = np.zeros((count_a, count_b))
    np.add.at(overlap, (a[both], b[both]), 1)
    if overlap.size == 0:
        return {}
    rows, cols = linear_sum_assignment(-overlap)
    return {int(c): int(r) for r, c in zip(rows, cols, strict=True) if overlap[r, c] > 0}


def _runs(flags: np.ndarray) -> list[tuple[int, int]]:
    padded = np.concatenate([[False], flags, [False]])
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(s), int(e)) for s, e in zip(edges[0::2], edges[1::2], strict=True)]


def compare_diarizations(
    first: Diarization,
    second: Diarization,
    duration_s: float,
    *,
    margin_s: float = DEFAULT_MARGIN_S,
) -> CompareResult:
    frames = ceil(duration_s / FRAME_S)
    names_a = {label: i for i, label in enumerate(first.labels())}
    names_b = {label: i for i, label in enumerate(second.labels())}
    a = _labels_per_frame(first.exclusive_turns, frames, names_a)
    b = _labels_per_frame(second.exclusive_turns, frames, names_b)
    mapping = _map_labels(a, b, len(names_a), len(names_b))
    mapped = np.array([mapping.get(int(x), -2) if x >= 0 else -1 for x in b], dtype=np.int32)
    ignore = _boundary_mask(first.exclusive_turns, frames, margin_s) | _boundary_mask(
        second.exclusive_turns, frames, margin_s
    )
    valid = ((a >= 0) | (b >= 0)) & ~ignore
    agree = valid & (a >= 0) & (a == mapped)
    disagree = valid & ~agree
    total = int(valid.sum())
    agreement = 1.0 if total == 0 else float(agree.sum()) / total
    runs = [(s * FRAME_S, e * FRAME_S) for s, e in _runs(disagree)]
    merged: list[tuple[float, float]] = []
    for start, end in runs:
        if merged and start - merged[-1][1] <= MERGE_GAP_S:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    spans = [(round(s, 2), round(e, 2)) for s, e in merged if e - s >= MIN_SPAN_S]
    return CompareResult(
        margin_s=margin_s,
        agreement=round(agreement, 4),
        disagreement_s=round(sum(e - s for s, e in spans), 2),
        spans=spans,
    )
