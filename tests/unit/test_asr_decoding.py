# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from saidby.engines.asr import faster_whisper as fw
from saidby.models import get_spec
from saidby.models import store as model_store
from saidby.runtime.device import DeviceInfo


class _StubModel:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    def transcribe(self, audio: np.ndarray, **kwargs: Any) -> tuple[list[Any], Any]:
        self.kwargs = kwargs
        return [], SimpleNamespace(language="es")


def _engine(monkeypatch: pytest.MonkeyPatch, deterministic: bool) -> tuple[Any, _StubModel]:
    spec = get_spec("asr:tiny")
    monkeypatch.setattr(model_store, "local_path", lambda s: spec.key)
    monkeypatch.setattr(model_store, "local_revision", lambda s: s.revision)
    engine = fw.FasterWhisperTranscriber("tiny", DeviceInfo("cpu"), deterministic=deterministic)
    stub = _StubModel()
    engine._model = stub
    return engine, stub


def test_default_decoding_keeps_whisper_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, stub = _engine(monkeypatch, False)
    engine.transcribe(np.zeros(16000, dtype=np.float32), language="es")
    assert "temperature" not in stub.kwargs
    assert "condition_on_previous_text" not in stub.kwargs


def test_deterministic_decoding_disables_sampling(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, stub = _engine(monkeypatch, True)
    engine.transcribe(np.zeros(16000, dtype=np.float32), language="es")
    assert stub.kwargs["temperature"] == 0.0
    assert stub.kwargs["condition_on_previous_text"] is False
