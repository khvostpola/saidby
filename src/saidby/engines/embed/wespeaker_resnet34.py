# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import pickle
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from saidby.engines._common import Stopwatch, release_memory, resolve_model
from saidby.formats.audio import SAMPLE_RATE
from saidby.models import store as model_store
from saidby.runtime.device import DeviceInfo
from saidby.schema.engine import EngineInfo

PREPROCESSING = "fbank80-cmn;l2;dur-weighted-mean;v1"
LEGACY_PREPROCESSING = "mono 16 kHz, l2-norm, weighted mean"
SAFE_PREFIXES = ("torch", "collections", "numpy", "_codecs", "builtins")


class _Stub:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __setstate__(self, state: Any) -> None:
        pass


class _SafeUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str) -> Any:
        if module.startswith("pyannote"):
            return type(name, (_Stub,), {})
        if module.startswith(SAFE_PREFIXES):
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"blocked global {module}.{name}")


_SAFE_PICKLE = SimpleNamespace(
    __name__="saidby_safe_pickle",
    Unpickler=_SafeUnpickler,
    load=pickle.load,
    UnpicklingError=pickle.UnpicklingError,
)


def load_state_dict(checkpoint: Path) -> dict[str, Any]:
    import torch

    data = torch.load(
        checkpoint, map_location="cpu", weights_only=False, pickle_module=_SAFE_PICKLE
    )
    state: dict[str, Any] = data["state_dict"]
    return {k.removeprefix("resnet."): v for k, v in state.items() if k.startswith("resnet.")}


class WeSpeakerResNet34Embedder:
    preprocessing = PREPROCESSING
    accepted_preprocessing: tuple[str, ...] = (PREPROCESSING, LEGACY_PREPROCESSING)

    def __init__(self, device: DeviceInfo, model: str = "wespeaker-resnet34") -> None:
        self.spec, self.path, key = resolve_model("embedder", model)
        self.device = device
        self._net: Any = None
        self.info = EngineInfo(
            kind="embedder",
            name="wespeaker-resnet34",
            model=key,
            repo_id=self.spec.repo_id if self.spec else None,
            revision=model_store.local_revision(self.spec) if self.spec else None,
            device=device.kind,
        )

    def load(self) -> float:
        from saidby.engines.embed._wespeaker_resnet import ResNet34

        with Stopwatch() as watch:
            net = ResNet34(feat_dim=80, embed_dim=256)
            net.load_state_dict(load_state_dict(self.path / "pytorch_model.bin"))
            self._net = net.to(self.device.kind).eval()
        return watch.seconds

    def unload(self) -> None:
        self._net = None
        release_memory()

    def embed(self, audio: np.ndarray, spans: list[tuple[float, float]]) -> np.ndarray:
        import torch
        from torchaudio.compliance import kaldi  # type: ignore[import-untyped]

        if self._net is None:
            self.load()
        rows = []
        with torch.inference_mode():
            for start, end in spans:
                chunk = torch.from_numpy(audio[int(start * SAMPLE_RATE) : int(end * SAMPLE_RATE)])
                feats = kaldi.fbank(
                    chunk.unsqueeze(0) * (1 << 15),
                    num_mel_bins=80,
                    frame_length=25.0,
                    frame_shift=10.0,
                    dither=0.0,
                    sample_frequency=SAMPLE_RATE,
                    window_type="hamming",
                    use_energy=False,
                )
                feats = feats - feats.mean(dim=0, keepdim=True)
                vec = self._net(feats.unsqueeze(0).to(self.device.kind))[0].float().cpu().numpy()
                rows.append(vec / np.linalg.norm(vec))
        return np.stack(rows) if rows else np.zeros((0, 256), dtype=np.float32)
