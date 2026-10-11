# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import sys
from typing import Annotated

import typer

from saidby import __version__
from saidby.cli import directory as directory_cli
from saidby.cli import models as models_cli
from saidby.cli import speakers as speakers_cli
from saidby.cli.doctor import doctor
from saidby.cli.enroll import enroll
from saidby.cli.process import process
from saidby.cli.review import review
from saidby.errors import SaidbyError

app = typer.Typer(
    name="saidby",
    help="Offline-first diarized transcription.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
app.add_typer(models_cli.app, name="models")
app.add_typer(speakers_cli.app, name="speakers")
app.add_typer(directory_cli.app, name="directory")
app.command("doctor")(doctor)
app.command("process")(process)
app.command("enroll")(enroll)
app.command("review")(review)


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def root(
    version: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True)] = False,
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
