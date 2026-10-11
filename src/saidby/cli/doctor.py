# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import platform
import sys
from typing import Annotated

import typer

from saidby import __version__
from saidby.models import REGISTRY
from saidby.models import store as model_store
from saidby.runtime.device import detect_cuda
from saidby.runtime.prepare import preload_cublas
from saidby.runtime.procs import tool_version


def doctor(
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output")] = False,
) -> None:
    """Check ffmpeg, GPU, CUDA libraries, installed models and offline settings."""
    cuda = detect_cuda()
    cublas = preload_cublas() if cuda else []
    report = {
        "saidby": __version__,
        "python": platform.python_version(),
        "platform": sys.platform,
        "ffmpeg": tool_version("ffmpeg"),
        "gpu": {"name": cuda.name, "vram_total_mb": cuda.vram_total_mb} if cuda else None,
        "cublas12_preloaded": cublas,
        "models": {s.key: model_store.is_installed(s) for s in REGISTRY},
        "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE") == "1",
        "hf_token_set": bool(os.environ.get("HF_TOKEN")),
        "llama_server": tool_version("llama-server", "--version"),
    }
    problems: list[str] = []
    if report["ffmpeg"] is None:
        problems.append("ffmpeg not found on PATH")
    if cuda and not cublas:
        problems.append(
            "GPU found but CUDA 12 cuBLAS wheels are missing (pip install nvidia-cublas-cu12)"
        )
    if as_json:
        typer.echo(json.dumps({**report, "problems": problems}, indent=2))
    else:
        for key, value in report.items():
            typer.echo(f"{key}: {value}")
        for problem in problems:
            typer.echo(f"problem: {problem}")
    raise typer.Exit(1 if problems else 0)
