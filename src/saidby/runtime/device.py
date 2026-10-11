# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import subprocess
from dataclasses import dataclass
from typing import Literal

from saidby.errors import UsageError
from saidby.runtime.procs import which

DeviceKind = Literal["cuda", "cpu"]


@dataclass(frozen=True)
class DeviceInfo:
    kind: DeviceKind
    name: str | None = None
    vram_total_mb: int | None = None


def detect_cuda() -> DeviceInfo | None:
    if which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None
    if not out:
        return None
    name, _, memory = out.splitlines()[0].partition(",")
    return DeviceInfo("cuda", name.strip(), int(memory) if memory.strip().isdigit() else None)


def resolve_device(requested: str = "auto") -> DeviceInfo:
    if requested not in {"auto", "cuda", "cpu"}:
        raise UsageError(f"unknown device: {requested}")
    if requested == "cpu":
        return DeviceInfo("cpu")
    cuda = detect_cuda()
    if cuda is not None:
        return cuda
    if requested == "cuda":
        raise UsageError("--device cuda requested but no NVIDIA GPU was found")
    return DeviceInfo("cpu")
