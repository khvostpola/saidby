# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Annotated

import typer

from saidby.cli.progress import Progress
from saidby.config.settings import Settings
from saidby.errors import StageError
from saidby.pipeline.runner import Pipeline


def process(
    inputs: Annotated[list[Path], typer.Argument(help="Audio or video files")],
    out: Annotated[Path, typer.Option("--out", help="Output folder")],
    config: Annotated[Path | None, typer.Option(help="Path to a saidby.toml")] = None,
    language: Annotated[str | None, typer.Option(help="Recording language, e.g. es")] = None,
    device: Annotated[str | None, typer.Option(help="auto, cuda or cpu")] = None,
    asr_model: Annotated[str | None, typer.Option(help="Model key or local path")] = None,
    compute_type: Annotated[str | None, typer.Option()] = None,
    deterministic: Annotated[
        bool, typer.Option("--deterministic", help="Reproducible decoding")
    ] = False,
    diarizer: Annotated[
        str | None, typer.Option(help="nemotron3, pyannote-community1 or fake")
    ] = None,
    num_speakers: Annotated[int | None, typer.Option(min=1)] = None,
    directory: Annotated[
        Path | None, typer.Option(help="Directory YAML with people and terms")
    ] = None,
    compare: Annotated[str | None, typer.Option(help="Second diarizer to compare against")] = None,
    bias_mode: Annotated[str | None, typer.Option(help="full or windows")] = None,
    no_identify: Annotated[bool, typer.Option("--no-identify")] = False,
    no_bias: Annotated[bool, typer.Option("--no-bias")] = False,
    no_transplant: Annotated[bool, typer.Option("--no-transplant")] = False,
    correct: Annotated[bool, typer.Option("--correct", help="Fix terms with a local LLM")] = False,
    llm_url: Annotated[str | None, typer.Option(help="OpenAI-compatible endpoint")] = None,
    llm_binary: Annotated[str | None, typer.Option(help="Path to llama-server")] = None,
    allow_remote_llm: Annotated[bool, typer.Option("--allow-remote-llm")] = False,
    identify_threshold: Annotated[float | None, typer.Option()] = None,
    keep_intermediates: Annotated[bool, typer.Option("--keep-intermediates")] = False,
    force: Annotated[bool, typer.Option("--force")] = False,
    fail_fast: Annotated[bool, typer.Option("--fail-fast")] = False,
    strict_offline: Annotated[bool, typer.Option("--strict-offline")] = False,
    progress: Annotated[str | None, typer.Option(help="human, json or none")] = None,
) -> None:
    """Transcribe recordings into one output folder each."""
    settings = Settings.load(
        config,
        {
            "language": language,
            "device": device,
            "asr_model": asr_model,
            "compute_type": compute_type,
            "deterministic": deterministic or None,
            "diarizer": diarizer,
            "num_speakers": num_speakers,
            "directory": directory,
            "identify": False if no_identify else None,
            "compare": compare,
            "bias_mode": bias_mode,
            "bias": False if no_bias else None,
            "transplant": False if no_transplant else None,
            "correct": correct or None,
            "llm_url": llm_url,
            "llm_binary": llm_binary,
            "allow_remote_llm": allow_remote_llm or None,
            "identify_threshold": identify_threshold,
            "keep_intermediates": keep_intermediates or None,
            "force": force or None,
            "fail_fast": fail_fast or None,
            "strict_offline": strict_offline or None,
            "progress": progress,
        },
    )
    results = Pipeline(settings, progress=Progress(settings.progress)).run(inputs, out)
    failed = [r for r in results if r.status != "ok"]
    if failed:
        code = failed[0].exit_code if len(failed) == 1 else StageError.exit_code
        raise typer.Exit(code)
