# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000
TURNS = (
    ("SPEAKER_00", 0.5, 3.0, 220.0),
    ("SPEAKER_01", 3.6, 6.0, 440.0),
    ("SPEAKER_00", 6.4, 8.2, 220.0),
    ("SPEAKER_01", 8.5, 9.8, 440.0),
)
DURATION_S = 10.0


def synthetic_audio(seed: int = 1234) -> np.ndarray:
    rng = np.random.default_rng(seed)
    audio = 0.002 * rng.standard_normal(int(DURATION_S * SAMPLE_RATE))
    for _, start, end, freq in TURNS:
        t = np.arange(int(start * SAMPLE_RATE), int(end * SAMPLE_RATE)) / SAMPLE_RATE
        audio[int(start * SAMPLE_RATE) : int(end * SAMPLE_RATE)] += 0.3 * np.sin(
            2 * np.pi * freq * t
        )
    return audio.astype(np.float32)


def synthetic_rttm(uri: str) -> str:
    return "".join(
        f"SPEAKER {uri} 1 {start:.3f} {end - start:.3f} <NA> <NA> {speaker} <NA> <NA>\n"
        for speaker, start, end, _ in TURNS
    )


def build_synthetic(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    sf.write(
        out / "tones_2spk_10s.flac", synthetic_audio(), SAMPLE_RATE, format="FLAC", subtype="PCM_16"
    )
    (out / "tones_2spk_10s.rttm").write_text(synthetic_rttm("tones_2spk_10s"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["synthetic"])
    parser.add_argument("--out", type=Path, default=Path("fixtures/synthetic"))
    args = parser.parse_args()
    build_synthetic(args.out)


if __name__ == "__main__":
    main()
