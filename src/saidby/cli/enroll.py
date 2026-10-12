# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from saidby.config.settings import Settings
from saidby.errors import UsageError
from saidby.formats.directory_yaml import load_directory
from saidby.speakers.enrollment import ConsentInput, enroll_voices, resolve_consents
from saidby.speakers.people import find_person

if TYPE_CHECKING:
    from saidby.schema.directory import Person


def _configured_directory() -> Path:
    configured = Settings.load().directory
    if not configured:
        raise UsageError("no directory file: pass --directory or set one in saidby.toml")
    return configured[-1]


def enroll(
    out_dir: Annotated[
        Path,
        typer.Argument(help="Output folder of a finished run (the one `saidby process` wrote)."),
    ],
    speaker: Annotated[list[str], typer.Option("--speaker", help="LABEL=PERSON (an id or a name)")],
    directory: Annotated[
        Path | None,
        typer.Option(help="Directory file to update (default: the last configured one)"),
    ] = None,
    consent_file: Annotated[
        Path | None, typer.Option(help="consent.yaml (default: next to the directory)")
    ] = None,
    consent_source: Annotated[str | None, typer.Option(help="How consent was given")] = None,
    consent_declared_by: Annotated[str | None, typer.Option(help="Who declared it")] = None,
    consent_date: Annotated[str | None, typer.Option(help="YYYY-MM-DD, default today")] = None,
    channel: Annotated[str, typer.Option(help="Recording channel label")] = "mobile-call",
    embedder_name: Annotated[
        str, typer.Option("--embedder", help="Voiceprint model.")
    ] = "wespeaker-resnet34",
    device: Annotated[str, typer.Option(help="auto, cuda or cpu.")] = "auto",
) -> None:
    """Store voiceprints of people who spoke in a finished run. Requires recorded consent."""
    parsed = [item.partition("=") for item in speaker]
    if any(not label or not person for label, _, person in parsed):
        raise UsageError("expected --speaker LABEL=PERSON (an id or a name)")
    directory = directory or _configured_directory()
    dir_model, raw = load_directory(directory)
    chosen: list[tuple[str, Person]] = []
    for label, _, key in parsed:
        person = find_person(dir_model, key)
        if person is None:
            raise UsageError(
                f"{key!r} is not in the directory; add the person first "
                "(saidby directory add-person)"
            )
        chosen.append((label, person))
    given = {}
    if consent_source and consent_declared_by:
        when = dt.date.fromisoformat(consent_date) if consent_date else None
        entry = ConsentInput(consent_source, consent_declared_by, when)
        given = {person.id: entry for _, person in chosen}
    consents = resolve_consents(
        [person for _, person in chosen],
        consent_file or directory.with_name("consent.yaml"),
        given,
    )
    backup = enroll_voices(
        out_dir,
        [(label, person.id) for label, person in chosen],
        directory,
        raw,
        consents,
        embedder_name=embedder_name,
        device=device,
        channel=channel,
        echo=typer.echo,
    )
    if backup:
        typer.echo(f"backup: {backup}")
