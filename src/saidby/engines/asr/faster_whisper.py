# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import faster_whisper
import numpy as np

from saidby.engines._common import Stopwatch, release_memory, resolve_model
from saidby.formats.audio import SAMPLE_RATE
from saidby.models import store as model_store
from saidby.runtime.device import DeviceInfo
from saidby.schema.engine import EngineInfo
from saidby.schema.transcript import Segment, Transcript, Word


class FasterWhisperTranscriber:
    def __init__(
        self, model: str, device: DeviceInfo, compute_type: str = "auto", beam_size: int = 5
    ) -> None:
        self.spec, self.path, key = resolve_model("asr", model)
        self.device = device
        self.compute_type = (
            compute_type
            if compute_type != "auto"
            else ("float16" if device.kind == "cuda" else "int8")
        )
        self.beam_size = beam_size
        self._model: faster_whisper.WhisperModel | None = None
        self.info = EngineInfo(
            kind="asr",
            name="faster-whisper",
            model=key,
            repo_id=self.spec.repo_id if self.spec else None,
            revision=model_store.local_revision(self.spec) if self.spec else None,
            device=device.kind,
            compute_type=self.compute_type,
            library=f"faster-whisper {faster_whisper.__version__}",
        )

    def load(self) -> float:
        with Stopwatch() as watch:
            self._model = faster_whisper.WhisperModel(
                str(self.path),
                device=self.device.kind,
                compute_type=self.compute_type,
                local_files_only=True,
            )
        return watch.seconds

    def unload(self) -> None:
        self._model = None
        release_memory()

    def transcribe(
        self,
        audio: np.ndarray,
        *,
        language: str | None,
        hotwords: str | None = None,
        initial_prompt: str | None = None,
    ) -> Transcript:
        if self._model is None:
            self.load()
        assert self._model is not None
        segments, info = self._model.transcribe(
            audio,
            language=language,
            word_timestamps=True,
            beam_size=self.beam_size,
            initial_prompt=initial_prompt,
            hotwords=hotwords,
        )
        built = []
        for seg in segments:
            words = [
                Word(start=w.start, end=w.end, word=w.word, p=round(w.probability, 3))
                for w in seg.words or []
            ]
            if words:
                built.append(Segment(start=seg.start, end=seg.end, words=words))
        return Transcript(
            language=info.language,
            duration_s=len(audio) / SAMPLE_RATE,
            engine=self.info,
            segments=built,
        )
