# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import contextlib
import importlib.util
import os
import socket
from pathlib import Path
from typing import ClassVar

import pytest

from saidby.errors import NetworkAttemptError, UsageError
from saidby.runtime import host, prepare
from saidby.runtime.device import resolve_device
from saidby.runtime.netguard import guard_network, is_loopback
from saidby.runtime.prepare import _preload_windows, nvidia_package_dirs, preload_cuda_libs


def test_prepare_sets_offline_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HF_HUB_OFFLINE", "PYANNOTE_METRICS_ENABLED", "HF_HUB_DISABLE_TELEMETRY"):
        monkeypatch.delenv(name, raising=False)
    first = prepare(want_cuda=False)
    second = prepare(want_cuda=False)
    assert first == second
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["PYANNOTE_METRICS_ENABLED"] == "false"
    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"


def test_is_loopback() -> None:
    assert is_loopback("127.0.0.1")
    assert is_loopback("::1")
    assert is_loopback("localhost")
    assert not is_loopback("huggingface.co")
    assert not is_loopback("1.1.1.1")


@pytest.mark.enable_socket
def test_netguard_blocks_remote_lookup() -> None:
    with guard_network() as guard, pytest.raises(NetworkAttemptError):
        socket.getaddrinfo("example.com", 443)
    assert guard.events == [("socket.getaddrinfo", "example.com")]


@pytest.mark.enable_socket
def test_netguard_records_without_raising() -> None:
    with guard_network(raise_on_attempt=False) as guard, contextlib.suppress(OSError):
        socket.getaddrinfo("example.invalid", 443)
    assert guard.events


@pytest.mark.enable_socket
def test_netguard_allows_loopback() -> None:
    with guard_network() as guard:
        socket.getaddrinfo("127.0.0.1", 80)
    assert guard.events == []


def test_device_cpu_and_invalid() -> None:
    assert resolve_device("cpu").kind == "cpu"
    with pytest.raises(UsageError):
        resolve_device("tpu")


def test_nvidia_wheel_folders_are_found_by_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "bin").mkdir()
    (tmp_path / "lib").mkdir()

    class Spec:
        submodule_search_locations: ClassVar[list[str]] = [str(tmp_path)]

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: Spec())
    assert nvidia_package_dirs("cublas", "bin") == [tmp_path / "bin"]
    assert nvidia_package_dirs("cublas", "lib") == [tmp_path / "lib"]
    assert nvidia_package_dirs("cublas", "share") == []
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert nvidia_package_dirs("cublas", "bin") == []

    def no_parent(name: str) -> None:
        raise ModuleNotFoundError("No module named 'nvidia'")

    monkeypatch.setattr(importlib.util, "find_spec", no_parent)
    assert nvidia_package_dirs("cublas", "bin") == []
    assert preload_cuda_libs() == []


def test_preloading_without_the_wheels_loads_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert preload_cuda_libs() == []
    assert _preload_windows() == []


def test_windows_sets_the_symlink_warning_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_HUB_DISABLE_SYMLINKS_WARNING", raising=False)
    monkeypatch.setattr(host, "is_windows", lambda: True)
    prepare(want_cuda=False)
    assert os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] == "1"
