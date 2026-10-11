# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from saidby.errors import InputError
from saidby.formats.audio import SAMPLE_RATE, read_audio
from saidby.runtime.procs import run_checked


@dataclass(frozen=True)
class IngestResult:
    wav: Path
    audio: np.ndarray
    sha256: str
    size_bytes: int
    duration_s: float


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest(media: Path, workdir: Path) -> IngestResult:
    if not media.is_file():
        raise InputError(f"input file not found: {media}")
    workdir.mkdir(parents=True, exist_ok=True)
    wav = workdir / "audio.wav"
    run_checked(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-i",
            str(media),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(wav),
        ]
    )
    audio = read_audio(wav)
    if audio.size == 0:
        raise InputError(f"no audio stream found in {media.name}")
    return IngestResult(
        wav=wav,
        audio=audio,
        sha256=file_sha256(media),
        size_bytes=media.stat().st_size,
        duration_s=sf.info(wav).duration,
    )
