# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from build_fixtures import SAMPLE_RATE, synthetic_audio, synthetic_rttm  # noqa: E402


def test_synthetic_fixture_matches_generator() -> None:
    data, rate = sf.read(ROOT / "fixtures/synthetic/tones_2spk_10s.flac", dtype="float32")
    assert rate == SAMPLE_RATE
    expected = synthetic_audio()
    assert data.shape == expected.shape
    assert np.max(np.abs(data - expected)) < 1e-3


def test_synthetic_rttm_matches_generator() -> None:
    path = ROOT / "fixtures/synthetic/tones_2spk_10s.rttm"
    assert path.read_text(encoding="utf-8") == synthetic_rttm("tones_2spk_10s")
