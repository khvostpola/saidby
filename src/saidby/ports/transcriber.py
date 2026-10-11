# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Protocol

import numpy as np

from saidby.schema.engine import EngineInfo
from saidby.schema.transcript import Transcript


class Transcriber(Protocol):
    info: EngineInfo

    def load(self) -> float: ...

    def unload(self) -> None: ...

    def transcribe(
        self,
        audio: np.ndarray,
        *,
        language: str | None,
        hotwords: str | None = None,
        initial_prompt: str | None = None,
    ) -> Transcript: ...
