# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import atexit
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from saidby.engines.llm.openai_compat import OpenAICompatClient
from saidby.errors import LlmUnavailableError
from saidby.models import get_spec
from saidby.models import store as model_store
from saidby.runtime.device import DeviceInfo
from saidby.schema.engine import EngineInfo

ENV_BINARY = "SAIDBY_LLAMA_SERVER"


def find_binary(explicit: str | None = None) -> str:
    candidate = explicit or os.environ.get(ENV_BINARY) or shutil.which("llama-server")
    if not candidate or (not Path(candidate).exists() and shutil.which(candidate) is None):
        raise LlmUnavailableError(
            "llama-server not found: install llama.cpp and put llama-server on PATH "
            f"or set {ENV_BINARY}"
        )
    return str(candidate)


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_healthy(url: str, timeout_s: float, proc: subprocess.Popen[Any]) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise LlmUnavailableError(f"llama-server exited early with code {proc.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if b'"ok"' in response.read():
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(1)
    raise LlmUnavailableError("llama-server did not become healthy in time")


class LlamaServerManager:
    def __init__(
        self,
        device: DeviceInfo,
        *,
        binary: str | None = None,
        model_key: str = "qwen3.5-9b-q4",
        context: int = 8192,
        log_path: Path | None = None,
        startup_timeout_s: float = 180.0,
    ) -> None:
        self.device = device
        self.binary = binary
        self.model_key = model_key
        self.context = context
        self.log_path = log_path
        self.startup_timeout_s = startup_timeout_s
        self._proc: subprocess.Popen[Any] | None = None
        self._client: OpenAICompatClient | None = None
        spec = get_spec(f"llm:{model_key}")
        self.spec = spec
        self.info = EngineInfo(
            kind="llm",
            name="llama-server",
            model=model_key,
            repo_id=spec.repo_id,
            revision=model_store.local_revision(spec),
            device=device.kind,
        )

    def check(self) -> None:
        find_binary(self.binary)
        model_store.local_path(self.spec)

    def start(self) -> None:
        binary = find_binary(self.binary)
        gguf = model_store.local_path(self.spec)
        port = free_loopback_port()
        argv = [
            binary,
            "-m",
            str(gguf),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "-ngl",
            "99" if self.device.kind == "cuda" else "0",
            "-c",
            str(self.context),
            "-fa",
            "on",
            "--jinja",
            "--chat-template-kwargs",
            '{"enable_thinking": false}',
            "--no-webui",
        ]
        log = self.log_path.open("ab") if self.log_path else subprocess.DEVNULL
        env = {**os.environ, "HF_HUB_OFFLINE": "1"}
        self._proc = subprocess.Popen(
            argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env
        )
        atexit.register(self.stop)
        try:
            wait_healthy(f"http://127.0.0.1:{port}/health", self.startup_timeout_s, self._proc)
        except LlmUnavailableError:
            self.stop()
            raise
        self._client = OpenAICompatClient(
            f"http://127.0.0.1:{port}", model_key=self.model_key, name="llama-server"
        )

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def complete_json(self, **kwargs: Any) -> dict[str, Any]:
        if self._client is None:
            self.start()
        assert self._client is not None
        return self._client.complete_json(**kwargs)
