# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from saidby.errors import UsageError
from saidby.ports.diarizer import Diarizer
from saidby.ports.transcriber import Transcriber
from saidby.runtime.device import DeviceInfo

TRANSCRIBERS = ("faster-whisper", "fake")
DIARIZERS = ("nemotron3", "pyannote-community1", "fake")


def make_transcriber(
    name: str, *, model: str, device: DeviceInfo, compute_type: str = "auto"
) -> Transcriber:
    if name == "faster-whisper":
        from saidby.engines.asr.faster_whisper import FasterWhisperTranscriber

        return FasterWhisperTranscriber(model, device, compute_type)
    if name == "fake":
        from saidby.engines.asr.fake import FakeTranscriber

        return FakeTranscriber()
    raise UsageError(f"unknown transcriber {name!r}; valid: {', '.join(TRANSCRIBERS)}")


def make_diarizer(name: str, *, device: DeviceInfo) -> Diarizer:
    if name == "nemotron3":
        from saidby.engines.diarize.nemotron3 import Nemotron3Diarizer

        return Nemotron3Diarizer(device)
    if name == "pyannote-community1":
        try:
            from saidby.engines.diarize.pyannote_community1 import PyannoteCommunity1Diarizer
        except ImportError as exc:
            raise UsageError("install the extra: pip install 'saidby[pyannote]'") from exc
        return PyannoteCommunity1Diarizer(device)
    if name == "fake":
        from saidby.engines.diarize.fake import FakeDiarizer

        return FakeDiarizer()
    raise UsageError(f"unknown diarizer {name!r}; valid: {', '.join(DIARIZERS)}")
