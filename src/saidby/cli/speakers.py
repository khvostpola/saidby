# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
from typing import Annotated

import typer

from saidby.cli.ui import Ui, interactive_streams
from saidby.config.settings import Settings
from saidby.errors import UsageError
from saidby.formats.directory_set import load_directory_set
from saidby.speakers import remap
from saidby.speakers.naming import person_id_for
from saidby.speakers.people import add_person_to_file, find_person

app = typer.Typer(
    help="Inspect, rename and merge speakers of a finished run.", no_args_is_help=True
)


def _ui() -> Ui:
    return Ui()


def _minutes(seconds: float) -> str:
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes}:{rest:02d}"


def _named_by(row: dict[str, object]) -> str:
    if row["identified"]:
        return f"voice {row['score']:.2f}" if isinstance(row["score"], float) else "voice"
    return "you" if row["name"] else "-"


def speaker_table(rows: list[dict[str, object]]) -> list[str]:
    header = ["speaker", "name", "speech", "named by", "track"]
    body = [
        [
            str(row["label"]),
            str(row["name"] or "-"),
            _minutes(float(str(row["speech_s"]))),
            _named_by(row),
            str(row["track"] or "-"),
        ]
        for row in rows
    ]
    widths = [max(len(line[i]) for line in [header, *body]) for i in range(len(header))]
    return [
        "  ".join(cell.ljust(width) for cell, width in zip(line, widths, strict=True)).rstrip()
        for line in [header, *body]
    ]


@app.command("show")
def show(
    out_dir: Annotated[
        Path,
        typer.Argument(help="Output folder of a finished run (the one `saidby process` wrote)."),
    ],
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
) -> None:
    """List the speakers of an output folder."""
    rows = remap.show(out_dir)
    if as_json:
        typer.echo(json.dumps(rows, indent=2))
    else:
        typer.echo("\n".join(speaker_table(rows)))


@app.command("map")
def map_speaker(
    out_dir: Annotated[
        Path,
        typer.Argument(help="Output folder of a finished run (the one `saidby process` wrote)."),
    ],
    assign: Annotated[
        list[str],
        typer.Option("--set", help='LABEL=PERSON (an id or a name) or LABEL="Free name"'),
    ],
    directory: Annotated[
        list[Path] | None,
        typer.Option(help="Directory to find people in (default: the configured ones)"),
    ] = None,
    add_missing: Annotated[
        bool,
        typer.Option(
            "--add-missing",
            help="Add names that are not in the directory to its last file, without asking.",
        ),
    ] = False,
) -> None:
    """Give speakers a person id and name without reprocessing audio."""
    files = directory or Settings.load().directory
    people = load_directory_set(files).merged if files else None
    for item in assign:
        label, _, target = item.partition("=")
        if not label or not target:
            raise UsageError(f"expected LABEL=VALUE, got {item!r}")
        person = find_person(people, target) if people else None
        if person is None and files and (add_missing or _offer_to_add(target, files[-1])):
            person, backup = add_person_to_file(files[-1], target)
            note = f" (backup: {backup})" if backup else ""
            typer.echo(f"added {person.id} ({person.name}) to {files[-1]}{note}")
            people = load_directory_set(files).merged
        if person is not None:
            remap.map_speaker(out_dir, label, person.id, person.name)
        else:
            remap.map_speaker(out_dir, label, person_id_for(target), target)
        typer.echo(f"{label} -> {target}")


def _offer_to_add(name: str, file: Path) -> bool:
    if not interactive_streams():
        return False
    return _ui().confirm(f"{name!r} is not in the directory. Add it to {file}?", default=True)


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
