# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import atexit
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
from pathlib import Path
from typing import IO, Any, Literal

from saidby.engines.llm.openai_compat import LOOPBACK_OPENER, OpenAICompatClient
from saidby.errors import InputError, LlmUnavailableError
from saidby.i18n import _
from saidby.models import get_spec
from saidby.models import store as model_store
from saidby.runtime.device import DeviceInfo
from saidby.runtime.procs import run_checked, spawn_managed
from saidby.schema.engine import EngineInfo

ENV_BINARY = "SAIDBY_LLAMA_SERVER"
LISTING_TIMEOUT_S = 60.0
NO_DEVICES = "(none)"


def find_binary(explicit: str | None = None) -> str:
    candidate = explicit or os.environ.get(ENV_BINARY) or shutil.which("llama-server")
    if not candidate or (not Path(candidate).exists() and shutil.which(candidate) is None):
        raise LlmUnavailableError(
            _(
                "llama-server not found: install llama.cpp and put llama-server on "
                "PATH or set {ENV_BINARY}"
            ).format(ENV_BINARY=ENV_BINARY)
        )
    return str(candidate)


def gpu_backends(binary: str) -> list[str] | None:
    """Backends of the GPUs `binary` can offload to; None when it will not say."""
    try:
        out = run_checked([binary, "--list-devices"], timeout=LISTING_TIMEOUT_S).stdout
    except (InputError, subprocess.TimeoutExpired, OSError):
        return None
    _, found, listing = out.partition("Available devices:")
    if not found:
        return None
    lines = [line.strip() for line in listing.splitlines() if line.strip() != NO_DEVICES]
    return [re.split(r"[^A-Za-z]", line, maxsplit=1)[0] for line in lines if line]


def engine_device(
    requested: Literal["cuda", "cpu"], backends: list[str] | None
) -> Literal["cuda", "cpu"] | None:
    if requested == "cpu":
        return "cpu"
    if backends is None:
        return None
    if "CUDA" in backends:
        return "cuda"
    return None if backends else "cpu"


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_healthy(url: str, timeout_s: float, proc: subprocess.Popen[Any]) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise LlmUnavailableError(
                _("llama-server exited early with code {returncode}").format(
                    returncode=proc.returncode
                )
            )
        try:
            with LOOPBACK_OPENER.open(url, timeout=2) as response:
                if b'"ok"' in response.read():
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(1)
    raise LlmUnavailableError(_("llama-server did not become healthy in time"))


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
        self._log: IO[bytes] | None = None
        self._client: OpenAICompatClient | None = None
        spec = get_spec(f"llm:{model_key}")
        self.spec = spec
        self.info = EngineInfo(
            kind="llm",
            name="llama-server",
            model=model_key,
            repo_id=spec.repo_id,
            revision=model_store.local_revision(spec),
            device="cpu" if device.kind == "cpu" else None,
        )

    def check(self) -> None:
        find_binary(self.binary)
        model_store.local_path(self.spec)

    def start(self) -> None:
        binary = find_binary(self.binary)
        gguf = model_store.local_path(self.spec)
        backends = gpu_backends(binary) if self.device.kind == "cuda" else None
        used = engine_device(self.device.kind, backends)
        self.info = self.info.model_copy(update={"device": used})
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
        self._log = self.log_path.open("ab") if self.log_path else None
        env = {**os.environ, "HF_HUB_OFFLINE": "1"}
        self._proc = spawn_managed(
            argv, stdout=self._log if self._log else subprocess.DEVNULL, env=env
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
        log, self._log = self._log, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        if log is not None:
            log.close()

    def complete_json(self, **kwargs: Any) -> dict[str, Any]:
        if self._client is None:
            self.start()
        assert self._client is not None
        return self._client.complete_json(**kwargs)
