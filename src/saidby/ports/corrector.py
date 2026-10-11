# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Protocol

from saidby.schema.engine import EngineInfo


class LlmTruncatedError(Exception):
    pass


class LlmClient(Protocol):
    info: EngineInfo

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout_s: float = 300.0,
    ) -> dict[str, Any]: ...
