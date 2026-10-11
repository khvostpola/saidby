# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import ipaddress
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from saidby.errors import NetworkAttemptError

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def is_loopback(host: object) -> bool:
    if not isinstance(host, str):
        return True
    if host in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class NetGuard:
    def __init__(self, *, raise_on_attempt: bool = True) -> None:
        self.raise_on_attempt = raise_on_attempt
        self.events: list[tuple[str, str]] = []
        self.active = False

    def _hook(self, event: str, args: tuple[Any, ...]) -> None:
        if not self.active:
            return
        if event == "socket.getaddrinfo":
            host = args[0]
        elif event == "socket.connect":
            address = args[1]
            if not isinstance(address, tuple):
                return
            host = address[0]
        else:
            return
        if is_loopback(host):
            return
        self.events.append((event, str(host)))
        if self.raise_on_attempt:
            raise NetworkAttemptError(f"outbound network attempt blocked: {event}")

    def __enter__(self) -> "NetGuard":
        sys.addaudithook(self._hook)
        self.active = True
        return self

    def __exit__(self, *exc: object) -> None:
        self.active = False


@contextmanager
def guard_network(*, raise_on_attempt: bool = True) -> Iterator[NetGuard]:
    with NetGuard(raise_on_attempt=raise_on_attempt) as guard:
        yield guard
