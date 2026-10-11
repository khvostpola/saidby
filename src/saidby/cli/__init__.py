# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import sys
from typing import Annotated

import typer

from saidby import __version__
from saidby.cli import models as models_cli
from saidby.cli.doctor import doctor
from saidby.cli.process import process
from saidby.errors import SaidbyError

app = typer.Typer(
    name="saidby",
    help="Offline-first diarized transcription.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
app.add_typer(models_cli.app, name="models")
app.command("doctor")(doctor)
app.command("process")(process)


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
