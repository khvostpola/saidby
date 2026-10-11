# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import numpy as np
import pytest

from saidby.formats.audio import SAMPLE_RATE, read_audio
from saidby.models import get_spec
from saidby.models import store as model_store
from saidby.runtime.device import resolve_device

CONV = Path(__file__).resolve().parents[2] / "fixtures/conversations/dev/dev-conv-01.flac"
SPANS = [(1.0, 6.0), (15.0, 22.0)]

pytestmark = [
    pytest.mark.models,
    pytest.mark.skipif(
        not model_store.is_installed(get_spec("embedder:wespeaker-resnet34")),
        reason="embedder model is not pulled",
    ),
]


def test_vendored_resnet_matches_pyannote() -> None:
    pytest.importorskip("pyannote.audio")
    import torch
    from pyannote.audio import Inference, Model

    from saidby.engines.embed.wespeaker_resnet34 import WeSpeakerResNet34Embedder

    audio = read_audio(CONV)
    mine = WeSpeakerResNet34Embedder(resolve_device("cpu")).embed(audio, SPANS)
    spec = get_spec("embedder:wespeaker-resnet34")
    model = Model.from_pretrained(spec.repo_id)
    assert model is not None
    reference = Inference(model, window="whole", device=torch.device("cpu"))
    for (start, end), vector in zip(SPANS, mine, strict=True):
        chunk = torch.from_numpy(audio[int(start * SAMPLE_RATE) : int(end * SAMPLE_RATE)])
        ref = np.asarray(
            reference({"waveform": chunk.unsqueeze(0), "sample_rate": SAMPLE_RATE})
        ).ravel()
        cosine = float(np.dot(ref / np.linalg.norm(ref), vector))
        assert cosine > 0.999
