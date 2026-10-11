# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import contextlib
import os
import socket

import pytest

from saidby.errors import NetworkAttemptError, UsageError
from saidby.runtime import prepare
from saidby.runtime.device import resolve_device
from saidby.runtime.netguard import guard_network, is_loopback


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
