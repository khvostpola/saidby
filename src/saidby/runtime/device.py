# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import ctypes
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

from saidby.errors import UsageError
from saidby.i18n import N_, _
from saidby.runtime import host
from saidby.runtime.prepare import preload_cuda_libs
from saidby.runtime.procs import which

DeviceKind = Literal["cuda", "cpu"]
DeviceReason = Literal["requested_cpu", "no_gpu", "gpu_unusable"]


def cpu_torch_hint() -> str:
    return (
        "this install has the CPU build of PyTorch; for the GPU reinstall with: "
        + host.gpu_install_command()
    )


@dataclass(frozen=True)
class DeviceInfo:
    kind: DeviceKind
    name: str | None = None
    vram_total_mb: int | None = None
    note: str | None = None
    reason: DeviceReason | None = None


@dataclass(frozen=True)
class GpuFacts:
    name: str
    vram_total_mb: int | None
    driver: str | None


def read_gpu() -> GpuFacts | None:
    if which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            stdin=subprocess.DEVNULL,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None
    if not out:
        return None
    parts = [p.strip() for p in out.splitlines()[0].split(",")]
    memory = parts[1] if len(parts) > 1 and parts[1].isdigit() else None
    return GpuFacts(parts[0], int(memory) if memory else None, parts[2] if len(parts) > 2 else None)


def torch_cuda_ready() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


def torch_build() -> str | None:
    try:
        import torch
    except ImportError:
        return None
    cuda = torch.version.cuda
    return f"cuda {cuda}" if cuda else "cpu"


def ct2_cuda_devices() -> int:
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


def _loadable(name: str) -> bool:
    try:
        if sys.platform == "win32":
            ctypes.CDLL(name, winmode=0)
        else:
            ctypes.CDLL(name)
    except OSError:
        return False
    return True


def cublas12_available() -> bool:
    loaded = preload_cuda_libs()
    if any("cublas" in name.lower() for name in loaded):
        return True
    return _loadable("cublas64_12.dll" if host.is_windows() else "libcublas.so.12")


def cudnn9_available() -> bool:
    return _loadable("cudnn64_9.dll" if host.is_windows() else "libcudnn.so.9")


def cuda_problems(gpu: GpuFacts | None) -> list[str]:
    if gpu is None:
        return [N_("no NVIDIA GPU found (nvidia-smi is missing or reports nothing)")]
    problems = []
    if torch_build() == "cpu":
        problems.append(cpu_torch_hint())
    elif not torch_cuda_ready():
        problems.append(N_("PyTorch cannot use the GPU (check the NVIDIA driver, 580 or newer)"))
    if ct2_cuda_devices() == 0:
        problems.append(N_("CTranslate2 cannot see the GPU"))
    elif not cublas12_available():
        problems.append(f"CUDA 12 cuBLAS libraries are missing: {host.gpu_install_command()}")
    elif not cudnn9_available():
        problems.append(f"cuDNN 9 libraries are missing: {host.gpu_install_command()}")
    return problems


def resolve_device(requested: str = "auto") -> DeviceInfo:
    if requested not in {"auto", "cuda", "cpu"}:
        raise UsageError(_("unknown device: {requested}").format(requested=requested))
    if requested == "cpu":
        return DeviceInfo("cpu", reason="requested_cpu")
    gpu = read_gpu()
    problems = cuda_problems(gpu)
    if gpu is not None and not problems:
        return DeviceInfo("cuda", gpu.name, gpu.vram_total_mb)
    if requested == "cuda":
        raise UsageError(
            _("--device cuda requested but the GPU is not usable: {problems}").format(
                problems="; ".join(problems)
            )
        )
    if gpu is None:
        return DeviceInfo("cpu", reason="no_gpu")
    return DeviceInfo("cpu", note="running on CPU: " + problems[0], reason="gpu_unusable")


def detect_cuda() -> DeviceInfo | None:
    device = resolve_device("auto")
    return device if device.kind == "cuda" else None
