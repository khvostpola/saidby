# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable
from typing import Any

from saidby.schema.engine import EngineInfo


class FakeLlmClient:
    def __init__(self, responder: Callable[[str, str], dict[str, Any]]) -> None:
        self.responder = responder
        self.calls: list[tuple[str, str]] = []
        self.started = False
        self.stopped = False
        self.info = EngineInfo(kind="llm", name="fake", model="fake")

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout_s: float = 300.0,
    ) -> dict[str, Any]:
        self.calls.append((system, user))
        return self.responder(system, user)
