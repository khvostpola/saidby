# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import numpy as np

from saidby.formats.audio import SAMPLE_RATE
from saidby.formats.rttm import read_rttm
from saidby.schema.diarization import Diarization, Turn, make_exclusive
from saidby.schema.engine import EngineInfo


class FakeDiarizer:
    def __init__(self, rttm: Path | None = None, turn_s: float = 5.0, speakers: int = 2) -> None:
        self.rttm = rttm
        self.turn_s = turn_s
        self.speakers = speakers
        self.info = EngineInfo(kind="diarizer", name="fake", model="fake")

    def load(self) -> float:
        return 0.0

    def unload(self) -> None:
        return None

    def diarize(
        self, audio: np.ndarray, *, uri: str, num_speakers: int | None = None
    ) -> Diarization:
        if self.rttm is not None:
            turns = read_rttm(self.rttm)
        else:
            duration = len(audio) / SAMPLE_RATE
            count = int(np.ceil(duration / self.turn_s))
            turns = [
                Turn(
                    start=i * self.turn_s,
                    end=min(duration, (i + 1) * self.turn_s),
                    label=f"SPEAKER_{i % self.speakers:02d}",
                )
                for i in range(count)
            ]
        return Diarization(
            uri=uri, engine=self.info, turns=turns, exclusive_turns=make_exclusive(turns)
        )
