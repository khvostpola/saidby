# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import numpy as np

from saidby.engines._common import Stopwatch, release_memory, resolve_model
from saidby.formats.audio import SAMPLE_RATE
from saidby.models import store as model_store
from saidby.runtime.device import DeviceInfo
from saidby.schema.diarization import Diarization, Turn
from saidby.schema.engine import EngineInfo


class PyannoteCommunity1Diarizer:
    def __init__(self, device: DeviceInfo, model: str = "pyannote-community1") -> None:
        self.spec, self.path, key = resolve_model("diarizer", model)
        self.device = device
        self._pipeline: Any = None
        self.info = EngineInfo(
            kind="diarizer",
            name="pyannote-community1",
            model=key,
            repo_id=self.spec.repo_id if self.spec else None,
            revision=model_store.local_revision(self.spec) if self.spec else None,
            device=device.kind,
        )

    def load(self) -> float:
        import torch
        from pyannote.audio import Pipeline

        with Stopwatch() as watch:
            self._pipeline = Pipeline.from_pretrained(str(self.path))
            self._pipeline.to(torch.device(self.device.kind))
        return watch.seconds

    def unload(self) -> None:
        self._pipeline = None
        release_memory()

    def diarize(
        self, audio: np.ndarray, *, uri: str, num_speakers: int | None = None
    ) -> Diarization:
        import torch

        if self._pipeline is None:
            self.load()
        output = self._pipeline(
            {
                "waveform": torch.from_numpy(audio).unsqueeze(0),
                "sample_rate": SAMPLE_RATE,
                "uri": uri,
            },
            num_speakers=num_speakers,
        )

        def to_turns(annotation: Any) -> list[Turn]:
            return [
                Turn(start=seg.start, end=seg.end, label=str(label))
                for seg, _, label in annotation.itertracks(yield_label=True)
            ]

        return Diarization(
            uri=uri,
            engine=self.info,
            turns=to_turns(output.speaker_diarization),
            exclusive_turns=to_turns(output.exclusive_speaker_diarization),
        )
