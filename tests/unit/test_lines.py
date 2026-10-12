# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os

import pytest

from saidby.cli.lines import activity_text, format_device, format_usage, loading_text
from saidby.cli.term import Terminal
from saidby.runtime.device import DeviceInfo
from saidby.runtime.usage import CpuUsage, GpuUsage

PLAIN = Terminal(tty=True, color=False, truecolor=False, columns=80)
COLOR = Terminal(tty=True, color=True, truecolor=False, columns=80)


def test_a_gpu_shows_its_name_memory_and_how_it_was_chosen() -> None:
    device = DeviceInfo("cuda", "NVIDIA GeForce RTX 4060 Laptop", 8188)
    assert format_device(device, "auto", PLAIN) == [
        "device      GPU · cuda · NVIDIA GeForce RTX 4060 Laptop · 8 GB   (auto → cuda)"
    ]
    assert format_device(device, "cuda", PLAIN)[0].endswith("(--device cuda)")


def test_a_gpu_without_a_name_or_memory_still_reads_well() -> None:
    assert format_device(DeviceInfo("cuda"), "auto", PLAIN)[0].startswith(
        "device      GPU · cuda   "
    )


def test_no_gpu_says_so() -> None:
    threads = os.cpu_count() or 1
    assert format_device(DeviceInfo("cpu", reason="no_gpu"), "auto", PLAIN) == [
        f"device      CPU · {threads} threads   (auto → cpu: no NVIDIA GPU found)"
    ]


def test_asking_for_the_cpu_is_not_a_warning() -> None:
    line = format_device(DeviceInfo("cpu", reason="requested_cpu"), "cpu", COLOR)[0]
    assert "\x1b[33m" not in line
    assert line.endswith("\x1b[2m(--device cpu)\x1b[0m")


def test_an_unusable_gpu_explains_and_points_to_doctor() -> None:
    device = DeviceInfo(
        "cpu",
        note="running on CPU: this install has the CPU build of PyTorch",
        reason="gpu_unusable",
    )
    lines = format_device(device, "auto", PLAIN)
    assert lines[0].endswith("(auto → cpu: the GPU cannot be used)")
    assert lines[1].strip() == "this install has the CPU build of PyTorch (details: saidby doctor)"
    assert lines[1].startswith(" " * 12)


def test_the_fallback_is_yellow_and_the_gpu_green() -> None:
    fallback = format_device(DeviceInfo("cpu", reason="no_gpu"), "auto", COLOR)[0]
    assert fallback.count("\x1b[33m") == 2
    gpu = format_device(DeviceInfo("cuda", "GPU", 8192), "auto", COLOR)[0]
    assert "\x1b[32mGPU · cuda · GPU · 8 GB\x1b[0m" in gpu


@pytest.mark.parametrize("terminal", [PLAIN])
def test_plain_output_has_no_escape_codes(terminal: Terminal) -> None:
    for device in (DeviceInfo("cuda", "GPU", 8192), DeviceInfo("cpu", reason="no_gpu")):
        assert all("\x1b" not in line for line in format_device(device, "auto", terminal))


def test_usage_text_for_each_device() -> None:
    assert format_usage(GpuUsage(5222, 8192, 93)) == "GPU 5.1/8.0 GB · 93%"
    assert format_usage(CpuUsage(8, 94)) == "CPU 8 threads · 94%"


def test_activity_and_loading_text() -> None:
    assert activity_text("asr") == "transcribing"
    assert activity_text("asr_bias") == "second pass with your terms"
    assert activity_text("something-new") == "working"
    assert loading_text("large-v3", DeviceInfo("cuda")) == "loading large-v3 into the GPU"
    assert loading_text("large-v3", DeviceInfo("cpu", reason="no_gpu")) == "loading large-v3"
    assert loading_text("large-v3", None) == "loading large-v3"
