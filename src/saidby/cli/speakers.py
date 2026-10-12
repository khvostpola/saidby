# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
from typing import Annotated

import typer

from saidby.cli.ui import Ui, auto_interactive, ensure_terminal
from saidby.config.settings import Settings
from saidby.errors import UsageError
from saidby.formats.directory_set import load_directory_set
from saidby.i18n import _
from saidby.interactive.flows import name_voices
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
        if isinstance(row["score"], float):
            return _("voice {score:.2f}").format(score=row["score"])
        return _("voice")
    return _("you") if row["name"] else "-"


def speaker_table(rows: list[dict[str, object]]) -> list[str]:
    header = [_("speaker"), _("name"), _("speech"), _("named by"), _("track")]
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
        list[str] | None,
        typer.Option("--set", help='LABEL=PERSON (an id or a name) or LABEL="Free name"'),
    ] = None,
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
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help=(
                "Listen to each voice and name it, with questions: the default on a terminal "
                "without --set. -i insists and fails without a terminal."
            ),
        ),
    ] = False,
) -> None:
    """Give speakers a person id and name without reprocessing audio."""
    settings = Settings.load()
    files = directory or settings.directory
    if interactive or (not assign and auto_interactive(settings)):
        _interactive_map(out_dir, assign, files)
        return
    if not assign:
        raise UsageError(_("pass --set LABEL=PERSON, or -i to listen and name each voice"))
    people = load_directory_set(files).merged if files else None
    for item in assign:
        label, _sep, target = item.partition("=")
        if not label or not target:
            raise UsageError(_("expected LABEL=VALUE, got {item!r}").format(item=item))
        person = find_person(people, target) if people else None
        offered = add_missing or (auto_interactive(settings) and _offer_to_add(target, files[-1]))
        if person is None and files and offered:
            person, backup = add_person_to_file(files[-1], target)
            note = f" (backup: {backup})" if backup else ""
            typer.echo(
                _("added {id} ({name}) to {value}{note}").format(
                    id=person.id, name=person.name, value=files[-1], note=note
                )
            )
            people = load_directory_set(files).merged
        if person is not None:
            remap.map_speaker(out_dir, label, person.id, person.name)
        else:
            remap.map_speaker(out_dir, label, person_id_for(target), target)
        typer.echo(f"{label} -> {target}")


def _interactive_map(out_dir: Path, assign: list[str] | None, files: list[Path]) -> None:
    if assign:
        raise UsageError(_("use either --set or -i, not both"))
    ensure_terminal(f"saidby speakers map {out_dir} --set SPEAKER_00=NAME")
    title = _("Speakers in {folder}").format(folder=out_dir)
    name_voices(_ui(), out_dir, files, title=title)


def _offer_to_add(name: str, file: Path) -> bool:
    question = _("{name!r} is not in the directory. Add it to {file}?").format(name=name, file=file)
    return _ui().confirm(question, default=True)


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
    typer.echo(_("merged {items} into {into}").format(items=", ".join(labels), into=into))
