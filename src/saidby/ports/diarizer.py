# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Protocol

import numpy as np

from saidby.schema.diarization import Diarization
from saidby.schema.engine import EngineInfo


class Diarizer(Protocol):
    info: EngineInfo

    def load(self) -> float: ...

    def unload(self) -> None: ...

    def diarize(
        self, audio: np.ndarray, *, uri: str, num_speakers: int | None = None
    ) -> Diarization: ...
