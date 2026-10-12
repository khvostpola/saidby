# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json

import pytest
from typer.testing import CliRunner

from saidby.cli import app
from saidby.errors import UsageError
from saidby.models import store as model_store
from saidby.runtime import device as dev
from saidby.runtime import diagnose, host
from saidby.runtime.device_cache import read_cache

runner = CliRunner()
GPU = dev.GpuFacts("Test GPU", 8000, "580.1")


def _world(
    monkeypatch: pytest.MonkeyPatch,
    *,
    gpu: dev.GpuFacts | None = GPU,
    build: str | None = "cuda 13.0",
    torch_ready: bool = True,
    ct2: int = 1,
    cublas: bool = True,
    cudnn: bool = True,
) -> None:
    monkeypatch.setattr(dev, "read_gpu", lambda: gpu)
    monkeypatch.setattr(dev, "torch_build", lambda: build)
    monkeypatch.setattr(dev, "torch_cuda_ready", lambda: torch_ready)
    monkeypatch.setattr(dev, "ct2_cuda_devices", lambda: ct2)
    monkeypatch.setattr(dev, "cublas12_available", lambda: cublas)
    monkeypatch.setattr(dev, "cudnn9_available", lambda: cudnn)


def test_usable_gpu_is_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch)
    device = dev.resolve_device("auto")
    assert (device.kind, device.name, device.note, device.reason) == (
        "cuda",
        "Test GPU",
        None,
        None,
    )
    assert dev.resolve_device("cuda").kind == "cuda"


def test_no_gpu_means_cpu_without_noise(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, gpu=None)
    device = dev.resolve_device("auto")
    assert (device.kind, device.note, device.reason) == ("cpu", None, "no_gpu")
    with pytest.raises(UsageError, match="no NVIDIA GPU"):
        dev.resolve_device("cuda")


def test_cpu_torch_with_a_gpu_present_falls_back_and_explains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _world(monkeypatch, build="cpu", torch_ready=False)
    device = dev.resolve_device("auto")
    assert device.kind == "cpu"
    assert device.reason == "gpu_unusable"
    assert device.note is not None
    assert "CPU build of PyTorch" in device.note
    with pytest.raises(UsageError, match="saidby\\[cuda\\]"):
        dev.resolve_device("cuda")


def test_missing_cublas_points_to_the_cuda_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, cublas=False)
    problems = dev.cuda_problems(GPU)
    assert any("saidby[cuda]" in p for p in problems)
    assert dev.resolve_device("auto").kind == "cpu"


def test_invisible_gpu_to_ctranslate2(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, ct2=0)
    assert any("CTranslate2" in p for p in dev.cuda_problems(GPU))


def test_checks_report_statuses_and_hints(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, build="cpu", torch_ready=False)
    monkeypatch.setattr(diagnose, "tool_version", lambda *a, **k: None)
    checks = {c.name: c for c in diagnose.run_checks()}
    assert checks["ffmpeg"].status == "fail"
    assert checks["ffmpeg"].hint
    assert checks["cuda"].status == "warn"
    assert checks["device"].detail == "auto selects the CPU"
    assert checks["llama-server"].status == "warn"
    assert checks["gpu"].status == "ok"


def test_old_driver_is_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dev, "torch_build", lambda: "cuda 13.0")
    assert diagnose.check_gpu(GPU).status == "ok"
    old = diagnose.check_gpu(dev.GpuFacts("Old", 8000, "535.1"))
    assert old.status == "warn"
    assert "580" in (old.hint or "")


def test_missing_models_fail_with_the_pull_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_store, "is_installed", lambda spec: False)
    first = diagnose.check_models()[0]
    assert first.status == "fail"
    assert first.hint == "run: saidby models pull --all"
    assert "asr:large-v3" in first.detail


def test_doctor_json_and_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, gpu=None)
    monkeypatch.setattr(model_store, "is_installed", lambda spec: False)
    result = runner.invoke(app, ["doctor", "--json"])
    report = json.loads(result.stdout)
    assert result.exit_code == 1
    assert {"checks", "problems", "models", "saidby"} <= report.keys()
    assert any(p.startswith("models:") for p in report["problems"])
    names = [c["name"] for c in report["checks"]]
    assert {"python", "ffmpeg", "gpu", "device", "models"} <= set(names)


def test_doctor_text_ends_ready_when_nothing_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, gpu=None)
    monkeypatch.setattr(model_store, "is_installed", lambda spec: True)
    monkeypatch.setattr(diagnose, "tool_version", lambda *a, **k: "ffmpeg version 7")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert result.stdout.rstrip().endswith("ready")


def test_smoke_test_skips_without_the_tiny_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_store, "is_installed", lambda spec: False)
    check = diagnose.smoke_test()
    assert check.status == "warn"
    assert "asr:tiny" in (check.hint or "")


def test_asking_for_the_cpu_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch)
    device = dev.resolve_device("cpu")
    assert (device.kind, device.reason, device.note) == ("cpu", "requested_cpu", None)


def test_doctor_remembers_the_verdict_for_the_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, build="cpu", torch_ready=False)
    assert read_cache() is None
    diagnose.check_device("auto")
    cached = read_cache()
    assert cached is not None
    assert (cached.kind, cached.reason) == ("cpu", "gpu_unusable")


def test_a_forced_cpu_check_says_nothing_about_the_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch)
    diagnose.check_device("cpu")
    assert read_cache() is None


def test_missing_cudnn_points_to_the_cuda_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, cudnn=False)
    problems = dev.cuda_problems(GPU)
    assert len(problems) == 1
    assert "cuDNN 9" in problems[0]
    assert 'uv tool install "saidby[cuda]"' in problems[0]


def test_the_gpu_hints_name_the_install_command_of_this_system(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host, "is_windows", lambda: False)
    assert dev.cpu_torch_hint().endswith('uv tool install "saidby[cuda]"')
    monkeypatch.setattr(host, "is_windows", lambda: True)
    hint = dev.cpu_torch_hint()
    assert "--index https://download.pytorch.org/whl/cu130" in hint
    assert "--index-strategy unsafe-best-match" in hint
    _world(monkeypatch, cublas=False)
    assert "download.pytorch.org" in dev.cuda_problems(GPU)[0]


def test_the_platform_row_leads_the_report(monkeypatch: pytest.MonkeyPatch) -> None:
    _world(monkeypatch, gpu=None)
    checks = diagnose.run_checks()
    assert checks[0].name == "platform"
    assert checks[0].status == "ok"
    assert checks[0].detail == host.platform_label()
    monkeypatch.setattr(host, "is_supported", lambda: False)
    untested = diagnose.check_platform()
    assert untested.status == "warn"
    assert "Linux and Windows" in (untested.hint or "")


def test_the_ffmpeg_hints_follow_the_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnose, "tool_version", lambda *a, **k: None)
    monkeypatch.setattr(diagnose, "which", lambda name: None)
    monkeypatch.setattr(host, "is_windows", lambda: True)
    assert "winget install ffmpeg" in (diagnose.check_ffmpeg().hint or "")
    assert "winget install ffmpeg" in (diagnose.check_ffplay().hint or "")
    monkeypatch.setattr(host, "is_windows", lambda: False)
    assert "dnf install ffmpeg" in (diagnose.check_ffmpeg().hint or "")


def test_the_llm_check_honours_the_binary_override(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def record(name: str, flag: str = "-version") -> str | None:
        seen.append(name)
        return "llama-server 1"

    monkeypatch.setattr(diagnose, "tool_version", record)
    monkeypatch.setenv("SAIDBY_LLAMA_SERVER", "/opt/llama/llama-server")
    assert diagnose.check_llm().status == "ok"
    assert seen == ["/opt/llama/llama-server"]
