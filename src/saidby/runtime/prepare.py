# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import contextlib
import ctypes
import glob
import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from saidby.runtime import host

CUBLAS_PATTERNS = ("libcublasLt.so.12*", "libcublas.so.12*")
WINDOWS_DLLS = {
    "cublas": ("cublasLt64_12.dll", "cublas64_12.dll"),
    "cudnn": ("cudnn64_9.dll",),
}
CUDNN_PARTS = "cudnn_*64_9.dll"
_dll_directories: list[Any] = []


@dataclass(frozen=True)
class RuntimeInfo:
    offline: bool
    cuda_preloaded: list[str] = field(default_factory=list)


def nvidia_package_dirs(package: str, subdir: str) -> list[Path]:
    """The `lib` or `bin` folders of an installed `nvidia-<package>-cu12` wheel."""
    try:
        spec = importlib.util.find_spec(f"nvidia.{package}")
    except ModuleNotFoundError:
        return []
    if spec is None or not spec.submodule_search_locations:
        return []
    folders = [Path(location) / subdir for location in spec.submodule_search_locations]
    return [folder for folder in folders if folder.is_dir()]


def _preload_posix() -> list[str]:
    loaded: list[str] = []
    for lib_dir in nvidia_package_dirs("cublas", "lib"):
        for pattern in CUBLAS_PATTERNS:
            for path in sorted(glob.glob(str(lib_dir / pattern))):
                ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
                loaded.append(Path(path).name)
    return loaded


def _preload_windows() -> list[str]:
    """CTranslate2 looks the DLLs up by name: register their folders and load them first."""
    if sys.platform != "win32":
        return []
    loaded: list[str] = []
    for package, names in WINDOWS_DLLS.items():
        for folder in nvidia_package_dirs(package, "bin"):
            _dll_directories.append(os.add_dll_directory(str(folder)))
            candidates = [folder / name for name in names]
            candidates += sorted(folder.glob(CUDNN_PARTS)) if package == "cudnn" else []
            for path in candidates:
                if path.is_file():
                    ctypes.CDLL(str(path))
                    loaded.append(path.name)
    return loaded


def preload_cuda_libs() -> list[str]:
    """Load the CUDA 12 libraries CTranslate2 needs and PyTorch does not bring."""
    return _preload_windows() if host.is_windows() else _preload_posix()


def prepare(*, offline: bool = True, want_cuda: bool = True) -> RuntimeInfo:
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("PYANNOTE_METRICS_ENABLED", "false")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    if host.is_windows():
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    loaded = preload_cuda_libs() if want_cuda else []
    return RuntimeInfo(offline=offline, cuda_preloaded=loaded)


def preload_runtime() -> None:
    for name in ("torch", "ctranslate2"):
        with contextlib.suppress(ImportError):
            importlib.import_module(name)
    if host.is_windows():
        with contextlib.suppress(OSError):
            preload_cuda_libs()
