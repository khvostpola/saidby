# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from saidby.cli.ui import Ui, ensure_terminal
from saidby.config.settings import Settings
from saidby.errors import UsageError
from saidby.formats.directory_yaml import load_directory
from saidby.i18n import _
from saidby.interactive.voices import store_voices
from saidby.speakers.enrollment import (
    DEFAULT_CHANNEL,
    ConsentInput,
    enroll_voices,
    ensure_audio,
    resolve_consents,
)
from saidby.speakers.people import find_person

if TYPE_CHECKING:
    from saidby.schema.directory import Person


def _configured_directory() -> Path:
    configured = Settings.load().directory
    if not configured:
        raise UsageError(_("no directory file: pass --directory or set one in saidby.toml"))
    return configured[-1]


def enroll(
    out_dir: Annotated[
        Path,
        typer.Argument(help="Output folder of a finished run (the one `saidby process` wrote)."),
    ],
    speaker: Annotated[
        list[str] | None,
        typer.Option("--speaker", help="LABEL=PERSON (an id or a name)"),
    ] = None,
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
    channel: Annotated[str, typer.Option(help="Recording channel label")] = DEFAULT_CHANNEL,
    embedder_name: Annotated[
        str, typer.Option("--embedder", help="Voiceprint model.")
    ] = "wespeaker-resnet34",
    device: Annotated[str, typer.Option(help="auto, cuda or cpu.")] = "auto",
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Ask for each named voice whether the person consented, instead of --speaker.",
        ),
    ] = False,
) -> None:
    """Store voiceprints of people who spoke in a finished run. Requires recorded consent."""
    if interactive:
        _interactive_enroll(
            out_dir,
            speaker,
            directory or _configured_directory(),
            consent_file,
            (consent_source, consent_declared_by, consent_date),
            channel=channel,
            embedder_name=embedder_name,
            device=device,
        )
        return
    if not speaker:
        raise UsageError(_("pass --speaker LABEL=PERSON, or -i to be asked for each voice"))
    parsed = [item.partition("=") for item in speaker]
    if any(not label or not person for label, _sep, person in parsed):
        raise UsageError(_("expected --speaker LABEL=PERSON (an id or a name)"))
    directory = directory or _configured_directory()
    dir_model, raw = load_directory(directory)
    chosen: list[tuple[str, Person]] = []
    for label, _sep, key in parsed:
        person = find_person(dir_model, key)
        if person is None:
            raise UsageError(
                _(
                    "{key!r} is not in the directory; add the person first (saidby "
                    "directory add-person)"
                ).format(key=key)
            )
        chosen.append((label, person))
    given = {}
    if consent_source and consent_declared_by:
        when = dt.date.fromisoformat(consent_date) if consent_date else None
        entry = ConsentInput(consent_source, consent_declared_by, when)
        given = {person.id: entry for _label, person in chosen}
    ensure_audio(out_dir)
    consents = resolve_consents(
        [person for _label, person in chosen],
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
        typer.echo(_("backup: {backup}").format(backup=backup))


def _interactive_enroll(
    out_dir: Path,
    speaker: list[str] | None,
    directory: Path,
    consent_file: Path | None,
    consent_flags: tuple[str | None, str | None, str | None],
    *,
    channel: str,
    embedder_name: str,
    device: str,
) -> None:
    if speaker:
        raise UsageError(_("use either --speaker or -i, not both"))
    if any(consent_flags):
        raise UsageError(
            _(
                "-i asks about consent itself; do not combine it with "
                "--consent-source, --consent-declared-by or --consent-date"
            )
        )
    ensure_terminal(
        f"saidby enroll {out_dir} --speaker SPEAKER_00=PERSON "
        "--consent-source SOURCE --consent-declared-by NAME"
    )
    store_voices(
        Ui(),
        out_dir,
        directory,
        consent_file or directory.with_name("consent.yaml"),
        embedder_name=embedder_name,
        device=device,
        channel=channel,
    )
