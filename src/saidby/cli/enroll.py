# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import datetime as dt
from pathlib import Path
from typing import Annotated

import typer

from saidby.config.settings import Settings
from saidby.errors import ConsentMissingError, InputError, UsageError
from saidby.formats.audio import read_audio
from saidby.formats.consent_yaml import append_consent, find_consent, load_consents
from saidby.formats.directory_yaml import load_directory, save_directory
from saidby.formats.manifest import read_manifest
from saidby.formats.rttm import read_rttm
from saidby.formats.words_json import read_transcript
from saidby.ports.registry import make_embedder
from saidby.runtime import prepare
from saidby.runtime.device import resolve_device
from saidby.schema.directory import ConsentRecord, Directory
from saidby.stages.identify import make_voiceprint, speaker_centroids
from saidby.stages.ingest import ingest


def _resolve_consents(
    person_ids: list[str],
    dir_model: Directory,
    consent_path: Path,
    source: str | None,
    declared_by: str | None,
    date: str | None,
) -> dict[str, ConsentRecord]:
    records, raw = load_consents(consent_path)
    resolved: dict[str, ConsentRecord] = {}
    for person_id in person_ids:
        person = dir_model.person(person_id)
        if person is None:
            raise UsageError(f"{person_id!r} is not in the directory; add the person first")
        record = find_consent(records, person.id, person.name)
        if record is None and source and declared_by:
            record = ConsentRecord(
                person=person.id,
                source=source,
                declared_by=declared_by,
                date=dt.date.fromisoformat(date) if date else dt.date.today(),
            )
            append_consent(consent_path, raw, record)
        if record is None:
            raise ConsentMissingError(
                f"no voiceprint consent recorded for {person.id}; pass --consent-source and "
                f"--consent-declared-by or add it to {consent_path}"
            )
        resolved[person_id] = record
    return resolved


def enroll(
    out_dir: Annotated[
        Path,
        typer.Argument(help="Output folder of a finished run (the one `saidby process` wrote)."),
    ],
    speaker: Annotated[list[str], typer.Option("--speaker", help="LABEL=PERSON_ID")],
    directory: Annotated[Path, typer.Option(help="Directory file to update")],
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
        raise UsageError("expected --speaker LABEL=PERSON_ID")
    dir_model, raw = load_directory(directory)
    consent_path = consent_file or directory.with_name("consent.yaml")
    resolved = _resolve_consents(
        [person for _, _, person in parsed],
        dir_model,
        consent_path,
        consent_source,
        consent_declared_by,
        consent_date,
    )

    prepare(offline=True, want_cuda=device != "cpu")
    settings = Settings.load(overrides={"device": device})
    manifest = read_manifest(out_dir / "manifest.json")
    transcript = read_transcript(out_dir / "transcript.words.json")
    wav = out_dir / ".work" / "audio.wav"
    if wav.exists():
        audio = read_audio(wav)
    else:
        source = Path(manifest.source.path)
        if not source.is_file():
            raise InputError(f"original recording not found: {source}")
        audio = ingest(source, out_dir / ".work").audio
    by_key = {key: s.label for s in transcript.speakers for key in (s.label, s.id) if key}
    ids = {s.label: s.file_id for s in transcript.speakers}
    spans: dict[str, list[tuple[float, float]]] = {}
    for turn in read_rttm(out_dir / "diarization.rttm"):
        label = by_key.get(turn.label)
        if label:
            spans.setdefault(label, []).append((turn.start, turn.end))
    embedder = make_embedder(embedder_name, device=resolve_device(settings.device))
    centroids = speaker_centroids(audio, spans, embedder)
    people = {p["id"]: p for p in raw["people"]}
    for label_arg, _, person_id in parsed:
        label = by_key.get(label_arg)
        if label is None or label not in centroids:
            raise UsageError(f"no usable speech for speaker {label_arg!r} (known: {sorted(ids)})")
        voiceprint = make_voiceprint(
            centroids[label], embedder, channel=channel, consent=resolved[person_id]
        )
        people[person_id]["voiceprint"] = voiceprint.model_dump(mode="json", exclude_none=True)
        typer.echo(f"{person_id}: {centroids[label].seconds} s of speech")
    backup = save_directory(directory, raw)
    if backup:
        typer.echo(f"backup: {backup}")
