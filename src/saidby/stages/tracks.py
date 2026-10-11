# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import numpy as np
import soundfile as sf

from saidby.formats.audio import SAMPLE_RATE
from saidby.schema.diarization import Turn

BLOCK_S = 60
FADE_S = 0.02


def _span_gain(start: int, end: int, lo: int, hi: int, fade: int) -> np.ndarray:
    idx = np.arange(lo, hi)
    gain = np.minimum((idx - start + 1) / fade, (end - idx) / fade)
    return np.clip(gain, 0.0, 1.0).astype(np.float32)


def render_track(path: Path, audio: np.ndarray, turns: list[Turn]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total = audio.shape[0]
    fade = max(1, int(FADE_S * SAMPLE_RATE))
    spans = sorted(
        (max(0, int(t.start * SAMPLE_RATE)), min(total, int(t.end * SAMPLE_RATE))) for t in turns
    )
    block = BLOCK_S * SAMPLE_RATE
    with sf.SoundFile(path, "w", SAMPLE_RATE, 1, format="FLAC", subtype="PCM_16") as out:
        for lo in range(0, total, block):
            hi = min(total, lo + block)
            buf = np.zeros(hi - lo, dtype=np.float32)
            for start, end in spans:
                if end <= lo or start >= hi:
                    continue
                a, b = max(start, lo), min(end, hi)
                piece = audio[a:b] * _span_gain(start, end, a, b, fade)
                current = buf[a - lo : b - lo]
                buf[a - lo : b - lo] = np.where(np.abs(piece) > np.abs(current), piece, current)
            out.write(buf)
