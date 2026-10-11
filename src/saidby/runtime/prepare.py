# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import ctypes
import glob
import importlib.util
import os
from dataclasses import dataclass, field
from pathlib import Path

CUBLAS_PATTERNS = ("libcublasLt.so.12*", "libcublas.so.12*")


@dataclass(frozen=True)
class RuntimeInfo:
    offline: bool
    cublas_preloaded: list[str] = field(default_factory=list)


def preload_cublas() -> list[str]:
    spec = importlib.util.find_spec("nvidia.cublas")
    if spec is None or not spec.submodule_search_locations:
        return []
    loaded: list[str] = []
    for location in spec.submodule_search_locations:
        lib_dir = Path(location) / "lib"
        for pattern in CUBLAS_PATTERNS:
            for path in sorted(glob.glob(str(lib_dir / pattern))):
                ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
                loaded.append(Path(path).name)
    return loaded


def prepare(*, offline: bool = True, want_cuda: bool = True) -> RuntimeInfo:
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("PYANNOTE_METRICS_ENABLED", "false")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    loaded = preload_cublas() if want_cuda else []
    return RuntimeInfo(offline=offline, cublas_preloaded=loaded)
