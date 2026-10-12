# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from saidby.errors import InputError
from saidby.runtime import host
from saidby.runtime.device import DeviceInfo
from saidby.runtime.procs import run_checked, which

GPU_QUERY = "memory.used,memory.total,utilization.gpu"
PROC_STAT = Path("/proc/stat")

Totals = tuple[int, int]


@dataclass(frozen=True)
class GpuUsage:
    used_mb: int
    total_mb: int
    util_pct: int


@dataclass(frozen=True)
class CpuUsage:
    threads: int
    util_pct: int


Usage = GpuUsage | CpuUsage
Probe = Callable[[], Usage | None]


def parse_gpu_usage(output: str) -> GpuUsage | None:
    first = output.strip().splitlines()[0] if output.strip() else ""
    try:
        used, total, util = (int(part.strip()) for part in first.split(","))
    except ValueError:
        return None
    return GpuUsage(used, total, util)


def read_gpu_usage(timeout: float = 2.0) -> GpuUsage | None:
    if which("nvidia-smi") is None:
        return None
    argv = ["nvidia-smi", f"--query-gpu={GPU_QUERY}", "--format=csv,noheader,nounits"]
    try:
        return parse_gpu_usage(run_checked(argv, timeout=timeout).stdout)
    except (InputError, OSError, subprocess.TimeoutExpired):
        return None


def _read_proc_stat() -> str:
    return PROC_STAT.read_text(encoding="utf-8")


def proc_stat_totals(reader: Callable[[], str] = _read_proc_stat) -> Totals | None:
    """(busy plus idle, idle) jiffies from the first line of /proc/stat."""
    try:
        fields = [int(x) for x in reader().splitlines()[0].split()[1:]]
    except (OSError, ValueError, IndexError):
        return None
    if len(fields) < 5:
        return None
    return sum(fields[:8]), fields[3] + fields[4]


def system_times_totals() -> Totals | None:
    """(kernel plus user, idle) in 100 ns ticks from GetSystemTimes; kernel time includes idle."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    ok = ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
    )
    if not ok:
        return None

    def ticks(moment: wintypes.FILETIME) -> int:
        return (moment.dwHighDateTime << 32) | moment.dwLowDateTime

    return ticks(kernel) + ticks(user), ticks(idle)


def cpu_totals() -> Totals | None:
    return system_times_totals() if host.is_windows() else proc_stat_totals()


class CpuMeter:
    def __init__(self, totals: Callable[[], Totals | None] = cpu_totals) -> None:
        self._totals = totals
        self._previous: Totals | None = None

    def sample(self) -> CpuUsage | None:
        now = self._totals()
        before, self._previous = self._previous, now
        if now is None or before is None:
            return None
        total, idle = now[0] - before[0], now[1] - before[1]
        if total <= 0:
            return None
        busy = round(100 * (total - idle) / total)
        return CpuUsage(os.cpu_count() or 1, max(0, min(100, busy)))


class Throttled:
    def __init__(
        self, probe: Probe, every_s: float = 1.0, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._probe = probe
        self._every_s = every_s
        self._clock = clock
        self._at = float("-inf")
        self._last: Usage | None = None

    def __call__(self) -> Usage | None:
        now = self._clock()
        if now - self._at >= self._every_s:
            self._at = now
            self._last = self._probe()
        return self._last


def probe_for(device: DeviceInfo) -> Probe:
    if device.kind == "cuda":
        return Throttled(read_gpu_usage)
    return Throttled(CpuMeter().sample)
