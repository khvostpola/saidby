# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
from typing import Annotated

import typer

from saidby.config.settings import Settings
from saidby.errors import UsageError
from saidby.formats.directory_set import load_directory_set
from saidby.speakers import remap
from saidby.speakers.naming import person_id_for

app = typer.Typer(
    help="Inspect, rename and merge speakers of a finished run.", no_args_is_help=True
)


@app.command("show")
def show(
    out_dir: Annotated[
        Path,
        typer.Argument(help="Output folder of a finished run (the one `saidby process` wrote)."),
    ],
) -> None:
    """List the speakers of an output folder."""
    typer.echo(json.dumps(remap.show(out_dir), indent=2))


@app.command("map")
def map_speaker(
    out_dir: Annotated[
        Path,
        typer.Argument(help="Output folder of a finished run (the one `saidby process` wrote)."),
    ],
    assign: Annotated[
        list[str], typer.Option("--set", help='LABEL=PERSON_ID or LABEL="Free name"')
    ],
    directory: Annotated[
        list[Path] | None,
        typer.Option(help="Directory to resolve person ids (default: the configured ones)"),
    ] = None,
) -> None:
    """Give speakers a person id and name without reprocessing audio."""
    files = directory or Settings.load().directory
    people = {p.id: p.name for p in load_directory_set(files).merged.people} if files else {}
    for item in assign:
        label, _, target = item.partition("=")
        if not label or not target:
            raise UsageError(f"expected LABEL=VALUE, got {item!r}")
        if target in people:
            remap.map_speaker(out_dir, label, target, people[target])
        else:
            remap.map_speaker(out_dir, label, person_id_for(target), target)
        typer.echo(f"{label} -> {target}")


@app.command("merge")
def merge(
    out_dir: Annotated[
        Path,
        typer.Argument(help="Output folder of a finished run (the one `saidby process` wrote)."),
    ],
    labels: Annotated[list[str], typer.Argument(help="Speakers to merge")],
    into: Annotated[str, typer.Option("--into", help="Speaker that keeps the merged speech")],
) -> None:
    """Merge speakers that the diarizer split by mistake."""
    remap.merge_speakers(out_dir, labels, into)
    typer.echo(f"merged {', '.join(labels)} into {into}")
