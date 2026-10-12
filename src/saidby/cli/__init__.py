# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import sys
from typing import Annotated

import typer

from saidby import __version__
from saidby.cli import directory as directory_cli
from saidby.cli import evaluate as evaluate_cli
from saidby.cli import models as models_cli
from saidby.cli import speakers as speakers_cli
from saidby.cli.doctor import doctor
from saidby.cli.enroll import enroll
from saidby.cli.init import init
from saidby.cli.process import EPILOG as PROCESS_EPILOG
from saidby.cli.process import process
from saidby.cli.review import review
from saidby.errors import SaidbyError

RUN = "Transcribe"
AFTER = "After a run"
SETUP = "Set up"
MEASURE = "Measure"

EPILOG = """\b
Start here:
  saidby doctor                         check this machine
  saidby models pull --all              download the models (needs the network)
  saidby process call.m4a              transcribe

Every command has its own help: saidby process --help, saidby review --help ...
Documentation: https://github.com/khvostpola/saidby/tree/main/docs"""

app = typer.Typer(
    name="saidby",
    help=(
        "Diarized transcription that runs on your machine: who said what and when, "
        "with your own names and terms spelled right."
    ),
    epilog=EPILOG,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.command("process", rich_help_panel=RUN, epilog=PROCESS_EPILOG)(process)
app.command("review", rich_help_panel=AFTER)(review)
app.command("enroll", rich_help_panel=AFTER)(enroll)
app.add_typer(speakers_cli.app, name="speakers", rich_help_panel=AFTER)
app.command("init", rich_help_panel=SETUP)(init)
app.command("doctor", rich_help_panel=SETUP)(doctor)
app.add_typer(models_cli.app, name="models", rich_help_panel=SETUP)
app.add_typer(directory_cli.app, name="directory", rich_help_panel=SETUP)
app.add_typer(evaluate_cli.app, name="eval", rich_help_panel=MEASURE)


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version, is_eager=True, help="Show the version and exit."
        ),
    ] = False,
) -> None:
    pass


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)
    except SaidbyError as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(exc.exit_code)
