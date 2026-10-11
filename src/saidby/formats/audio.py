# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000


def read_audio(path: Path) -> np.ndarray:
    data, rate = sf.read(path, dtype="float32", always_2d=False)
    if rate != SAMPLE_RATE:
        raise ValueError(f"expected {SAMPLE_RATE} Hz audio, got {rate}")
    return np.asarray(data, dtype=np.float32)
