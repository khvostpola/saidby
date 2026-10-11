# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import socket
import stat
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest

from saidby.engines.llm.llama_server import LlamaServerManager, find_binary
from saidby.engines.llm.openai_compat import OpenAICompatClient, is_local_url
from saidby.errors import LlmUnavailableError
from saidby.models import get_spec
from saidby.models import store as model_store
from saidby.ports.corrector import LlmTruncatedError
from saidby.runtime.device import DeviceInfo

pytestmark = pytest.mark.enable_socket

FAKE_SERVER = """#!/usr/bin/env python3
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(sys.argv[sys.argv.index("--port") + 1])


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send({"status": "ok"})

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self._send({"choices": [{"message": {"content": json.dumps({"changes": []})}}]})


HTTPServer(("127.0.0.1", port), H).serve_forever()
"""


class _Handler(BaseHTTPRequestHandler):
    reply: ClassVar[Any] = {"choices": [{"message": {"content": '{"changes": []}'}}]}
    seen: ClassVar[list[dict[str, Any]]] = []

    def log_message(self, *args: Any) -> None:
        return None

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        _Handler.seen.append(json.loads(self.rfile.read(length)))
        data = json.dumps(_Handler.reply).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def server() -> Iterator[str]:
    _Handler.seen = []
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_client_sends_schema_and_parses_json(server: str) -> None:
    client = OpenAICompatClient(server)
    result = client.complete_json(system="sys", user="usr", schema={"type": "object"})
    assert result == {"changes": []}
    body = _Handler.seen[0]
    assert body["temperature"] == 0
    assert body["response_format"]["json_schema"]["schema"] == {"type": "object"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_client_reports_truncated_json(server: str) -> None:
    _Handler.reply = {"choices": [{"message": {"content": '{"changes": [{"start": 1'}}]}
    with pytest.raises(LlmTruncatedError):
        OpenAICompatClient(server).complete_json(system="s", user="u", schema={})
    _Handler.reply = {"choices": [{"message": {"content": '{"changes": []}'}}]}


def test_client_reports_unreachable_endpoint() -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(LlmUnavailableError):
        OpenAICompatClient(f"http://127.0.0.1:{port}").complete_json(
            system="s", user="u", schema={}
        )


def test_local_url_detection() -> None:
    assert is_local_url("http://127.0.0.1:8080")
    assert is_local_url("http://localhost:8089")
    assert not is_local_url("https://api.example.com/v1")


def test_find_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SAIDBY_LLAMA_SERVER", raising=False)
    monkeypatch.setenv("PATH", "")
    with pytest.raises(LlmUnavailableError, match="SAIDBY_LLAMA_SERVER"):
        find_binary()


def test_manager_starts_serves_and_stops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binary = tmp_path / "llama-server"
    binary.write_text(FAKE_SERVER)
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"x")
    monkeypatch.setattr(model_store, "local_path", lambda spec: gguf)
    monkeypatch.setattr(model_store, "local_revision", lambda spec: spec.revision)
    manager = LlamaServerManager(DeviceInfo("cpu"), binary=str(binary), startup_timeout_s=20)
    manager.check()
    manager.start()
    try:
        proc = manager._proc
        assert proc is not None
        assert proc.poll() is None
        assert manager.complete_json(system="s", user="u", schema={}) == {"changes": []}
        assert manager.info.name == "llama-server"
        assert manager.info.model == "qwen3.5-9b-q4"
    finally:
        manager.stop()
    assert proc.poll() is not None
    manager.stop()


def test_manager_fails_cleanly_when_process_dies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "llama-server"
    binary.write_text("#!/bin/sh\nexit 3\n")
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"x")
    monkeypatch.setattr(model_store, "local_path", lambda spec: gguf)
    manager = LlamaServerManager(DeviceInfo("cpu"), binary=str(binary), startup_timeout_s=10)
    with pytest.raises(LlmUnavailableError, match="exited early"):
        manager.start()
    assert manager._proc is None


def test_registry_has_llm_model() -> None:
    assert get_spec("llm:qwen3.5-9b-q4").filename == "Qwen3.5-9B-Q4_K_M.gguf"
    assert os.name == "posix"
