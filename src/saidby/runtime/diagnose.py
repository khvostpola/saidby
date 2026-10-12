# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import importlib.util
import os
import platform
import shutil
import time
from dataclasses import dataclass
from typing import Literal

import numpy as np

from saidby.i18n import _
from saidby.models import REGISTRY
from saidby.models import store as model_store
from saidby.runtime import device as dev
from saidby.runtime import host
from saidby.runtime.device_cache import write_cache
from saidby.runtime.procs import tool_version, which

Status = Literal["ok", "warn", "fail"]
MIN_DRIVER = 580
MIN_FREE_GB = 15
SMOKE_SECONDS = 4


@dataclass(frozen=True)
class Check:
    name: str
    status: Status
    detail: str
    hint: str | None = None


def _driver_major(driver: str | None) -> int | None:
    try:
        return int((driver or "").split(".")[0])
    except ValueError:
        return None


def check_platform() -> Check:
    label = host.platform_label()
    if host.is_supported():
        return Check("platform", "ok", label)
    return Check(
        "platform", "warn", label, _("saidby supports Linux and Windows; this system is untested")
    )


def check_python() -> Check:
    version = platform.python_version()
    ok = tuple(int(x) for x in version.split(".")[:2]) >= (3, 12)
    return Check(
        "python",
        "ok" if ok else "fail",
        version,
        None if ok else _("saidby needs Python 3.12 or newer"),
    )


def check_ffmpeg() -> Check:
    version = tool_version("ffmpeg")
    if version is None:
        return Check(
            "ffmpeg",
            "fail",
            _("not found on PATH"),
            _("install ffmpeg (for example: {command})").format(command=host.ffmpeg_install_hint()),
        )
    return Check("ffmpeg", "ok", version.split(" Copyright")[0])


def check_ffplay() -> Check:
    if which("ffplay") is None:
        return Check(
            "ffplay",
            "warn",
            _(
                "not found: listening to samples in interactive mode "
                "will show the file path instead"
            ),
            _("ffplay comes with ffmpeg on most systems (for example: {command})").format(
                command=host.ffmpeg_install_hint()
            ),
        )
    return Check("ffplay", "ok", _("found"))


def check_gpu(gpu: dev.GpuFacts | None) -> Check:
    if gpu is None:
        return Check(
            "gpu",
            "warn",
            _("no NVIDIA GPU found; processing will run on the CPU, much slower"),
        )
    memory = f", {gpu.vram_total_mb} MB" if gpu.vram_total_mb else ""
    driver = _(", driver {version}").format(version=gpu.driver) if gpu.driver else ""
    major = _driver_major(gpu.driver)
    if major is not None and major < MIN_DRIVER and dev.torch_build() not in (None, "cpu"):
        return Check(
            "gpu",
            "warn",
            f"{gpu.name}{memory}{driver}",
            _("update the NVIDIA driver to {minimum} or newer").format(minimum=MIN_DRIVER),
        )
    return Check("gpu", "ok", f"{gpu.name}{memory}{driver}")


def check_runtime(gpu: dev.GpuFacts | None) -> list[Check]:
    build = dev.torch_build()
    checks = [Check("torch", "ok" if build else "fail", build or _("not installed"))]
    problems = dev.cuda_problems(gpu)
    if gpu is None:
        return checks
    status: Status = "ok" if not problems else "warn"
    detail = (
        _("GPU is usable by PyTorch and CTranslate2")
        if not problems
        else _("GPU present but not usable")
    )
    hint = None if not problems else _(problems[0])
    checks.append(Check("cuda", status, detail, hint))
    return checks


def check_device(requested: str = "auto") -> Check:
    try:
        device = dev.resolve_device(requested)
    except Exception as exc:
        return Check("device", "fail", str(exc))
    if requested != "cpu":
        write_cache(device)
    if device.kind == "cuda":
        return Check("device", "ok", _("auto selects the GPU ({name})").format(name=device.name))
    return Check("device", "ok", _("auto selects the CPU"), device.note)


def check_models() -> list[Check]:
    defaults = [s for s in REGISTRY if s.default]
    missing = [s.key for s in defaults if not model_store.is_installed(s)]
    optional = [s.key for s in REGISTRY if not s.default and model_store.is_installed(s)]
    detail = (
        _("all default models are installed")
        if not missing
        else _("missing: {models}").format(models=", ".join(missing))
    )
    status: Status = "ok" if not missing else "fail"
    hint = None if not missing else _("run: saidby models pull --all")
    checks = [Check("models", status, detail, hint)]
    if optional:
        checks.append(
            Check("extra models", "ok", _("installed: {models}").format(models=", ".join(optional)))
        )
    return checks


def check_disk(missing_models: bool) -> Check:
    from huggingface_hub import constants

    path = constants.HF_HUB_CACHE
    probe = path
    while not os.path.exists(probe) and probe != os.path.dirname(probe):
        probe = os.path.dirname(probe)
    free = shutil.disk_usage(probe).free / 1e9
    if missing_models and free < MIN_FREE_GB:
        return Check(
            "disk",
            "warn",
            _("{free:.0f} GB free for the model cache").format(free=free),
            _("the default models need about {needed} GB").format(needed=MIN_FREE_GB),
        )
    return Check("disk", "ok", _("{free:.0f} GB free for the model cache").format(free=free))


def check_extras() -> list[Check]:
    labels = {
        "pyannote": _('pyannote.audio (alternative diarizer): pip install "saidby[pyannote]"'),
        "jiwer": _('evaluation: pip install "saidby[eval]"'),
    }
    out = []
    for module, hint in labels.items():
        present = importlib.util.find_spec(module) is not None
        name = "pyannote extra" if module == "pyannote" else "eval extra"
        out.append(
            Check(
                name,
                "ok" if present else "warn",
                _("installed") if present else _("not installed"),
                None if present else hint,
            )
        )
    return out


def check_llm() -> Check:
    binary = os.environ.get("SAIDBY_LLAMA_SERVER") or "llama-server"
    version = tool_version(binary, "--version")
    if version is None:
        return Check(
            "llama-server",
            "warn",
            _("not found (only needed for --correct)"),
            _("install llama.cpp and put llama-server on PATH or set SAIDBY_LLAMA_SERVER"),
        )
    return Check("llama-server", "ok", version)


def check_environment() -> list[Check]:
    offline = os.environ.get("HF_HUB_OFFLINE") == "1"
    token = bool(os.environ.get("HF_TOKEN"))
    return [
        Check(
            "offline",
            "ok",
            _("processing always runs offline; only `saidby models pull` uses the network")
            + (_(" (HF_HUB_OFFLINE is set in this shell)") if offline else ""),
        ),
        Check(
            "hf token",
            "ok" if token else "warn",
            _("set") if token else _("not set (needed only for gated models such as pyannote)"),
        ),
    ]


def smoke_test(requested: str = "auto") -> Check:
    from saidby.engines.asr.faster_whisper import FasterWhisperTranscriber
    from saidby.models import get_spec
    from saidby.runtime.prepare import prepare

    if not model_store.is_installed(get_spec("asr:tiny")):
        return Check(
            "smoke test",
            "warn",
            _("skipped: asr:tiny is not installed"),
            _("run: saidby models pull asr:tiny"),
        )
    prepare(offline=True, want_cuda=True)
    try:
        device = dev.resolve_device(requested)
        engine = FasterWhisperTranscriber("tiny", device)
        started = time.perf_counter()
        load_s = engine.load()
        rng = np.random.default_rng(0)
        audio = (0.01 * rng.standard_normal(16000 * SMOKE_SECONDS)).astype(np.float32)
        engine.transcribe(audio, language="en")
        total = time.perf_counter() - started
        engine.unload()
    except Exception as exc:
        return Check(
            "smoke test",
            "fail",
            f"{type(exc).__name__}: {exc}",
            _("run `saidby doctor` again after fixing the problems above"),
        )
    return Check(
        "smoke test",
        "ok",
        _(
            "transcribed {seconds} s of audio with asr:tiny on the {kind} "
            "(load {load:.1f} s, total {total:.1f} s)"
        ).format(seconds=SMOKE_SECONDS, kind=device.kind, load=load_s, total=total),
    )


def run_checks(smoke: bool = False, requested: str = "auto") -> list[Check]:
    gpu = dev.read_gpu()
    checks = [
        check_platform(),
        check_python(),
        check_ffmpeg(),
        check_ffplay(),
        check_gpu(gpu),
        *check_runtime(gpu),
        check_device(requested),
    ]
    models = check_models()
    checks += models
    checks.append(check_disk(models[0].status == "fail"))
    checks += [*check_extras(), check_llm(), *check_environment()]
    if smoke:
        checks.append(smoke_test(requested))
    return checks
