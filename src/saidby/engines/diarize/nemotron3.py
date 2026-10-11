# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Iterator
from typing import Any

import numpy as np

from saidby.engines._common import Stopwatch, release_memory, resolve_model
from saidby.formats.audio import SAMPLE_RATE
from saidby.models import store as model_store
from saidby.runtime.device import DeviceInfo
from saidby.schema.diarization import Diarization, Turn, make_exclusive
from saidby.schema.engine import EngineInfo
from saidby.schema.ids import speaker_label


class Nemotron3Diarizer:
    def __init__(self, device: DeviceInfo, model: str = "nemotron3") -> None:
        self.spec, self.path, key = resolve_model("diarizer", model)
        self.device = device
        self._processor: Any = None
        self._model: Any = None
        self.mode = "offline"
        import transformers

        self.info = EngineInfo(
            kind="diarizer",
            name="nemotron3",
            model=key,
            repo_id=self.spec.repo_id if self.spec else None,
            revision=model_store.local_revision(self.spec) if self.spec else None,
            device=device.kind,
            library=f"transformers {transformers.__version__}",
        )

    def load(self) -> float:
        from transformers import AutoModelForAudioFrameClassification, AutoProcessor

        with Stopwatch() as watch:
            self._processor = AutoProcessor.from_pretrained(  # type: ignore[no-untyped-call]
                str(self.path), local_files_only=True
            )
            model = AutoModelForAudioFrameClassification.from_pretrained(
                str(self.path), local_files_only=True
            )
            self._model = model.to(self.device.kind).eval()
        return watch.seconds

    def unload(self) -> None:
        self._processor = None
        self._model = None
        release_memory()

    def _offline(self, audio: np.ndarray) -> list[dict[str, Any]]:
        processor, model = self._processor, self._model
        inputs = processor(audio, sampling_rate=SAMPLE_RATE).to(model.device, dtype=model.dtype)
        logits = model(**inputs).logits
        speakers: list[dict[str, Any]] = processor.extract_speaker_dict(
            logits, inputs.attention_mask
        )[0]
        return speakers

    def _streaming(self, audio: np.ndarray) -> list[dict[str, Any]]:
        import torch

        processor, model = self._processor, self._model

        def chunks() -> Iterator[Any]:
            yield processor(
                audio[: processor.num_samples_first_audio_chunk],
                sampling_rate=SAMPLE_RATE,
                is_streaming=True,
                is_first_audio_chunk=True,
            )
            frame = processor.num_mel_frames_per_step
            start = processor.audio_chunk_start(frame)
            while (end := start + processor.num_samples_per_audio_chunk) <= audio.shape[0]:
                yield processor(
                    audio[start:end],
                    sampling_rate=SAMPLE_RATE,
                    is_streaming=True,
                    is_first_audio_chunk=False,
                )
                frame += processor.num_mel_frames_per_step
                start = processor.audio_chunk_start(frame)
            yield processor(
                audio[start:],
                sampling_rate=SAMPLE_RATE,
                is_streaming=True,
                is_first_audio_chunk=False,
                is_last_audio_chunk=True,
            )

        cache, logits = None, []
        for inputs in chunks():
            outputs = model(**inputs.to(model.device, dtype=model.dtype), speaker_cache=cache)
            logits.append(outputs.logits)
            cache = outputs.speaker_cache
        speakers: list[dict[str, Any]] = processor.extract_speaker_dict(torch.cat(logits, dim=1))[0]
        return speakers

    def diarize(
        self, audio: np.ndarray, *, uri: str, num_speakers: int | None = None
    ) -> Diarization:
        import torch

        if self._model is None:
            self.load()
        with torch.inference_mode():
            try:
                segments = self._offline(audio)
                self.mode = "offline"
            except torch.OutOfMemoryError:
                release_memory()
                segments = self._streaming(audio)
                self.mode = "streaming"
        turns = [
            Turn(
                start=float(s["Start"]), end=float(s["End"]), label=speaker_label(int(s["Speaker"]))
            )
            for s in segments
        ]
        return Diarization(
            uri=uri, engine=self.info, turns=turns, exclusive_turns=make_exclusive(turns)
        )
