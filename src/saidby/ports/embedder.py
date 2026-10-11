# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Protocol

import numpy as np

from saidby.schema.engine import EngineInfo


class Embedder(Protocol):
    info: EngineInfo
    preprocessing: str
    accepted_preprocessing: tuple[str, ...]

    def load(self) -> float: ...

    def unload(self) -> None: ...

    def embed(self, audio: np.ndarray, spans: list[tuple[float, float]]) -> np.ndarray: ...
