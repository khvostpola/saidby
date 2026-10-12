# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from saidby.errors import LlmUnavailableError
from saidby.i18n import _
from saidby.ports.corrector import LlmTruncatedError
from saidby.runtime.netguard import is_loopback
from saidby.schema.engine import EngineInfo

LOOPBACK_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def is_local_url(url: str) -> bool:
    return is_loopback(urlparse(url).hostname)


def opener_for(url: str) -> urllib.request.OpenerDirector:
    """Loopback never goes through a proxy; Windows would otherwise send it there."""
    return LOOPBACK_OPENER if is_local_url(url) else urllib.request.build_opener()


class OpenAICompatClient:
    def __init__(
        self, base_url: str, *, model_key: str = "local", name: str = "openai-compatible"
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.info = EngineInfo(kind="llm", name=name, model=model_key)

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

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
        body = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "changes", "schema": schema},
            },
        }
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get("SAIDBY_LLM_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions", data=json.dumps(body).encode(), headers=headers
        )
        try:
            with opener_for(self.base_url).open(request, timeout=timeout_s) as response:
                content = json.load(response)["choices"][0]["message"]["content"]
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise LlmUnavailableError(
                _("LLM endpoint {base_url} is not reachable: {exc}").format(
                    base_url=self.base_url, exc=exc
                )
            ) from exc
        try:
            parsed: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LlmTruncatedError(_("LLM returned incomplete JSON")) from exc
        return parsed
