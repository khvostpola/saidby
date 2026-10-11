# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import hashlib

import numpy as np

from saidby.formats.audio import SAMPLE_RATE
from saidby.schema.engine import EngineInfo

DIM = 16


def vector_for(key: str) -> np.ndarray:
    seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "little")
    vec = np.random.default_rng(seed).standard_normal(DIM).astype(np.float32)
    return vec / np.linalg.norm(vec)


class FakeEmbedder:
    preprocessing = "fake;v1"
    accepted_preprocessing: tuple[str, ...] = ("fake;v1",)

    def __init__(self, voices: dict[tuple[float, float], str] | None = None) -> None:
        self.voices = voices or {}
        self.info = EngineInfo(kind="embedder", name="fake", model="fake", revision="0" * 40)

    def load(self) -> float:
        return 0.0

    def unload(self) -> None:
        return None

    def embed(self, audio: np.ndarray, spans: list[tuple[float, float]]) -> np.ndarray:
        rows = []
        for start, end in spans:
            key = next(
                (name for (s, e), name in self.voices.items() if s <= (start + end) / 2 <= e),
                f"unknown-{int(start * SAMPLE_RATE)}",
            )
            rows.append(vector_for(key))
        return np.stack(rows) if rows else np.zeros((0, DIM), dtype=np.float32)
