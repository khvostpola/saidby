# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import numpy as np

from saidby.formats.audio import SAMPLE_RATE
from saidby.schema.engine import EngineInfo
from saidby.schema.transcript import Segment, Transcript, Word


class FakeTranscriber:
    def __init__(self, words_per_second: float = 2.0) -> None:
        self.words_per_second = words_per_second
        self.info = EngineInfo(kind="asr", name="fake", model="fake")

    def load(self) -> float:
        return 0.0

    def unload(self) -> None:
        return None

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def transcribe(
        self,
        audio: np.ndarray,
        *,
        language: str | None,
        hotwords: str | None = None,
        initial_prompt: str | None = None,
    ) -> Transcript:
        duration = len(audio) / SAMPLE_RATE
        step = 1.0 / self.words_per_second
        count = int(duration / step)
        words = [
            Word(
                start=round(i * step, 3),
                end=round(i * step + step * 0.8, 3),
                word=f" word{i}",
                p=1.0,
            )
            for i in range(count)
        ]
        segments = [
            Segment(start=chunk[0].start, end=chunk[-1].end, words=chunk)
            for chunk in (words[i : i + 8] for i in range(0, len(words), 8))
        ]
        return Transcript(
            language=language, duration_s=duration, engine=self.info, segments=segments
        )
