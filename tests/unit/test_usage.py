# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import subprocess

import pytest

from saidby.errors import InputError
from saidby.runtime import usage
from saidby.runtime.device import DeviceInfo
from saidby.runtime.usage import CpuMeter, CpuUsage, GpuUsage, Throttled, parse_gpu_usage


def test_nvidia_smi_output_is_parsed() -> None:
    assert parse_gpu_usage("5123, 8188, 93\n") == GpuUsage(5123, 8188, 93)


def test_only_the_first_gpu_counts() -> None:
    assert parse_gpu_usage("100, 8188, 3\n7000, 24576, 99\n") == GpuUsage(100, 8188, 3)


@pytest.mark.parametrize("text", ["", "\n", "garbage", "1, 2", "[N/A], 8188, 0", "1, 2, 3, 4"])
def test_unreadable_output_is_no_sample(text: str) -> None:
    assert parse_gpu_usage(text) is None


def test_reading_the_gpu_runs_nvidia_smi(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(
        argv: list[str], *, timeout: float | None = None
    ) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="14, 8188, 14\n")

    monkeypatch.setattr(usage, "which", lambda name: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(usage, "run_checked", fake_run)
    assert usage.read_gpu_usage() == GpuUsage(14, 8188, 14)
    assert seen[0][0] == "nvidia-smi"
    assert "--query-gpu=memory.used,memory.total,utilization.gpu" in seen[0]


def test_no_nvidia_smi_means_no_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(usage, "which", lambda name: None)
    assert usage.read_gpu_usage() is None


def test_a_failing_nvidia_smi_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(argv: list[str], *, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        raise InputError("nvidia-smi failed")

    monkeypatch.setattr(usage, "which", lambda name: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(usage, "run_checked", boom)
    assert usage.read_gpu_usage() is None


def _stat(user: int, idle: int) -> str:
    return f"cpu  {user} 0 0 {idle} 0 0 0 0 0 0\ncpu0 1 2 3\n"


def test_cpu_load_comes_from_the_difference_between_two_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads = iter([_stat(100, 900), _stat(190, 910)])
    monkeypatch.setattr(os, "cpu_count", lambda: 8)
    meter = CpuMeter(lambda: next(reads))
    assert meter.sample() is None
    assert meter.sample() == CpuUsage(threads=8, util_pct=90)


def test_idle_time_including_iowait_is_not_load(monkeypatch: pytest.MonkeyPatch) -> None:
    first = "cpu  100 0 0 900 0 0 0 0\n"
    second = "cpu  100 0 0 900 100 0 0 0\n"
    reads = iter([first, second])
    monkeypatch.setattr(os, "cpu_count", lambda: 4)
    meter = CpuMeter(lambda: next(reads))
    meter.sample()
    assert meter.sample() == CpuUsage(4, 0)


@pytest.mark.parametrize("bad", ["", "cpu", "cpu 1 2", "nonsense here"])
def test_a_broken_proc_stat_is_no_sample(bad: str) -> None:
    meter = CpuMeter(lambda: bad)
    assert meter.sample() is None
    assert meter.sample() is None


def test_no_time_passed_is_no_sample() -> None:
    meter = CpuMeter(lambda: _stat(100, 900))
    meter.sample()
    assert meter.sample() is None


def test_samples_are_throttled() -> None:
    clock = [0.0]
    calls: list[int] = []

    def probe() -> GpuUsage:
        calls.append(1)
        return GpuUsage(len(calls), 8, 0)

    throttled = Throttled(probe, every_s=1.0, clock=lambda: clock[0])
    assert throttled() == GpuUsage(1, 8, 0)
    clock[0] = 0.5
    assert throttled() == GpuUsage(1, 8, 0)
    clock[0] = 1.2
    assert throttled() == GpuUsage(2, 8, 0)
    assert len(calls) == 2


def test_the_probe_matches_the_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(usage, "read_gpu_usage", lambda: GpuUsage(1, 2, 3))
    assert usage.probe_for(DeviceInfo("cuda", "GPU", 8188))() == GpuUsage(1, 2, 3)
    cpu = usage.probe_for(DeviceInfo("cpu", reason="no_gpu"))
    assert cpu() is None


def test_a_timeout_is_no_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(argv: list[str], *, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(argv, timeout or 0)

    monkeypatch.setattr(usage, "which", lambda name: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(usage, "run_checked", slow)
    assert usage.read_gpu_usage() is None
