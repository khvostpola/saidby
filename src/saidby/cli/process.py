# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Annotated

import typer

from saidby.cli.progress import Progress
from saidby.config.settings import Settings
from saidby.errors import StageError
from saidby.pipeline.runner import Pipeline

IO = "Input and output"
ASR = "Speech recognition"
SPEAKERS = "Speakers"
GLOSSARY = "Glossary and correction"
BEHAVIOR = "Run behavior"
PRIVACY = "Privacy"

EPILOG = """\b
Examples:
  saidby process call.m4a --language es
  saidby process a.mp4 b.mp3 --directory directory.yaml
  saidby process call.m4a --out results/ --directory directory.yaml --correct
  saidby process call.m4a --device cpu --asr-model tiny

Each input gets its own folder under the output folder (./saidby unless you pass --out or set
`out` in saidby.toml). A failed run keeps its work and the next run resumes from the last
finished stage."""


def process(
    inputs: Annotated[
        list[Path], typer.Argument(help="Audio or video files (anything ffmpeg reads).")
    ],
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            help="Folder for the results, one subfolder per input (default: ./saidby).",
            rich_help_panel=IO,
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(help="A saidby.toml with defaults for the options below.", rich_help_panel=IO),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option(
            help="Recording language code (es, en, pt...). Detected from the audio if omitted.",
            rich_help_panel=ASR,
        ),
    ] = None,
    device: Annotated[
        str | None,
        typer.Option(
            help="auto (default): GPU if usable, else CPU. Or force cuda or cpu.",
            rich_help_panel=ASR,
        ),
    ] = None,
    asr_model: Annotated[
        str | None,
        typer.Option(
            help="Recognition model: large-v3 (default), tiny, or a path to a CTranslate2 model.",
            rich_help_panel=ASR,
        ),
    ] = None,
    compute_type: Annotated[
        str | None,
        typer.Option(
            help="auto (float16 on GPU, int8 on CPU), float16, int8, int8_float16 or float32.",
            rich_help_panel=ASR,
        ),
    ] = None,
    deterministic: Annotated[
        bool,
        typer.Option(
            "--deterministic",
            help="Same input, same output: temperature 0 and no conditioning on earlier text.",
            rich_help_panel=ASR,
        ),
    ] = False,
    diarizer: Annotated[
        str | None,
        typer.Option(
            help="Who-spoke-when engine: nemotron3 (default) or pyannote-community1 (extra).",
            rich_help_panel=SPEAKERS,
        ),
    ] = None,
    num_speakers: Annotated[
        int | None,
        typer.Option(
            min=1, help="Fix the number of speakers when you know it.", rich_help_panel=SPEAKERS
        ),
    ] = None,
    compare: Annotated[
        str | None,
        typer.Option(
            help="Also run this second diarizer and record where the two disagree.",
            rich_help_panel=SPEAKERS,
        ),
    ] = None,
    no_identify: Annotated[
        bool,
        typer.Option(
            "--no-identify",
            help="Do not name speakers even if the directory has voiceprints.",
            rich_help_panel=SPEAKERS,
        ),
    ] = False,
    identify_threshold: Annotated[
        float | None,
        typer.Option(
            help="Minimum voiceprint similarity to assign a name (default 0.5).",
            rich_help_panel=SPEAKERS,
        ),
    ] = None,
    directory: Annotated[
        Path | None,
        typer.Option(
            help="Directory YAML with people, voiceprints and terms; turns on the glossary.",
            rich_help_panel=GLOSSARY,
        ),
    ] = None,
    no_bias: Annotated[
        bool,
        typer.Option(
            "--no-bias",
            help="Skip the second, hotword-biased recognition pass.",
            rich_help_panel=GLOSSARY,
        ),
    ] = False,
    bias_mode: Annotated[
        str | None,
        typer.Option(
            help="full (default) biases all audio; windows (experimental) only near likely terms.",
            rich_help_panel=GLOSSARY,
        ),
    ] = None,
    no_transplant: Annotated[
        bool,
        typer.Option(
            "--no-transplant",
            help="Run the biased pass but do not merge its terms into the transcript.",
            rich_help_panel=GLOSSARY,
        ),
    ] = False,
    correct: Annotated[
        bool,
        typer.Option(
            "--correct",
            help="Let a local LLM fix directory terms, within strict limits. Needs llama-server.",
            rich_help_panel=GLOSSARY,
        ),
    ] = False,
    llm_url: Annotated[
        str | None,
        typer.Option(
            help="Use an OpenAI-compatible server you already run, not llama-server.",
            rich_help_panel=GLOSSARY,
        ),
    ] = None,
    llm_binary: Annotated[
        str | None,
        typer.Option(
            help="Path to llama-server (default: PATH or SAIDBY_LLAMA_SERVER).",
            rich_help_panel=GLOSSARY,
        ),
    ] = None,
    allow_remote_llm: Annotated[
        bool,
        typer.Option(
            "--allow-remote-llm",
            help="Allow an LLM endpoint that is not on this machine.",
            rich_help_panel=GLOSSARY,
        ),
    ] = False,
    keep_intermediates: Annotated[
        bool,
        typer.Option(
            "--keep-intermediates",
            help="Keep the .work folder after success (it is kept on failure).",
            rich_help_panel=BEHAVIOR,
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite an output folder that holds results for a different input.",
            rich_help_panel=BEHAVIOR,
        ),
    ] = False,
    fail_fast: Annotated[
        bool,
        typer.Option(
            "--fail-fast", help="Stop at the first input that fails.", rich_help_panel=BEHAVIOR
        ),
    ] = False,
    progress: Annotated[
        str | None,
        typer.Option(
            help="human (default, on stderr), json (one event per line on stdout) or none.",
            rich_help_panel=BEHAVIOR,
        ),
    ] = None,
    strict_offline: Annotated[
        bool,
        typer.Option(
            "--strict-offline",
            help="Fail with exit code 8 if anything tries to leave this machine.",
            rich_help_panel=PRIVACY,
        ),
    ] = False,
) -> None:
    """Turn recordings into transcripts with speakers, timestamps and a track per speaker."""
    settings = Settings.load(
        config,
        {
            "out": out,
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
    results = Pipeline(settings, progress=Progress(settings.progress)).run(inputs, settings.out)
    failed = [r for r in results if r.status != "ok"]
    if failed:
        code = failed[0].exit_code if len(failed) == 1 else StageError.exit_code
        raise typer.Exit(code)
