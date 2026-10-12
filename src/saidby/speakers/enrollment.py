# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import datetime as dt
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from saidby.config.settings import Settings
from saidby.errors import ConsentMissingError, InputError, UsageError
from saidby.formats.audio import read_audio
from saidby.formats.consent_yaml import append_consent, find_consent, load_consents
from saidby.formats.directory_yaml import save_directory
from saidby.formats.manifest import read_manifest
from saidby.formats.rttm import read_rttm
from saidby.formats.words_json import read_transcript
from saidby.i18n import _
from saidby.ports.registry import make_embedder
from saidby.runtime import prepare
from saidby.runtime.device import resolve_device
from saidby.schema.directory import ConsentRecord, Person
from saidby.stages.identify import make_voiceprint, speaker_centroids
from saidby.stages.ingest import ingest

DEFAULT_CHANNEL = "mobile-call"


@dataclass(frozen=True)
class ConsentInput:
    source: str
    declared_by: str
    date: dt.date | None = None


@dataclass(frozen=True)
class PendingConsent:
    record: ConsentRecord
    is_new: bool


def prepare_consents(
    people: list[Person], consent_path: Path, provided: Mapping[str, ConsentInput]
) -> dict[str, PendingConsent]:
    records, _raw = load_consents(consent_path)
    pending: dict[str, PendingConsent] = {}
    for person in people:
        record = find_consent(records, person.id, person.name)
        given = provided.get(person.id)
        is_new = record is None and given is not None
        if record is None and given is not None:
            record = ConsentRecord(
                person=person.id,
                source=given.source,
                declared_by=given.declared_by,
                date=given.date or dt.date.today(),
            )
        if record is None:
            raise ConsentMissingError(
                _(
                    "no voiceprint consent recorded for {id}; pass --consent-source and "
                    "--consent-declared-by or add it to {consent_path}"
                ).format(id=person.id, consent_path=consent_path)
            )
        pending[person.id] = PendingConsent(record, is_new)
    return pending


def record_consents(consent_path: Path, pending: Mapping[str, PendingConsent]) -> None:
    fresh = [p.record for p in pending.values() if p.is_new]
    if not fresh:
        return
    _records, raw = load_consents(consent_path)
    for record in fresh:
        append_consent(consent_path, raw, record)


def resolve_consents(
    people: list[Person], consent_path: Path, provided: Mapping[str, ConsentInput]
) -> dict[str, ConsentRecord]:
    pending = prepare_consents(people, consent_path, provided)
    record_consents(consent_path, pending)
    return {person_id: item.record for person_id, item in pending.items()}


def _audio_files(out_dir: Path) -> tuple[Path | None, Path]:
    manifest = read_manifest(out_dir / "manifest.json")
    source = Path(manifest.source.path)
    kept = out_dir / ".work" / "audio.wav"
    if kept.exists():
        return kept, source
    if not source.is_file():
        raise InputError(
            _(
                "original recording not found: {source}; run this from the folder "
                "where you ran saidby process, or run the process again with "
                "--keep-intermediates"
            ).format(source=source)
        )
    return None, source


def ensure_audio(out_dir: Path) -> None:
    _audio_files(out_dir)


@contextmanager
def _audio_of(out_dir: Path) -> Iterator[np.ndarray]:
    kept, source = _audio_files(out_dir)
    if kept is not None:
        yield read_audio(kept)
        return
    with tempfile.TemporaryDirectory(prefix="saidby-") as scratch:
        yield ingest(source, Path(scratch)).audio


def enroll_voices(
    out_dir: Path,
    assignments: list[tuple[str, str]],
    directory_file: Path,
    raw: Any,
    pending: Mapping[str, PendingConsent],
    consent_file: Path,
    *,
    embedder_name: str,
    device: str,
    channel: str,
    echo: Callable[[str], None],
) -> Path | None:
    prepare(offline=True, want_cuda=device != "cpu")
    settings = Settings.load(overrides={"device": device})
    transcript = read_transcript(out_dir / "transcript.words.json")
    by_key = {key: s.label for s in transcript.speakers for key in (s.label, s.id) if key}
    spans: dict[str, list[tuple[float, float]]] = {}
    for turn in read_rttm(out_dir / "diarization.rttm"):
        label = by_key.get(turn.label)
        if label:
            spans.setdefault(label, []).append((turn.start, turn.end))
    embedder = make_embedder(embedder_name, device=resolve_device(settings.device))
    with _audio_of(out_dir) as audio:
        centroids = speaker_centroids(audio, spans, embedder)
    labels: dict[str, str] = {}
    for label_arg, person_id in assignments:
        label = by_key.get(label_arg)
        if label is None or label not in centroids:
            known = sorted({s.label for s in transcript.speakers})
            raise UsageError(
                _("no usable speech for speaker {label_arg!r} (known: {known})").format(
                    label_arg=label_arg, known=known
                )
            )
        labels[person_id] = label
    record_consents(consent_file, pending)
    people = {p["id"]: p for p in raw["people"]}
    for person_id, label in labels.items():
        voiceprint = make_voiceprint(
            centroids[label], embedder, channel=channel, consent=pending[person_id].record
        )
        people[person_id]["voiceprint"] = voiceprint.model_dump(mode="json", exclude_none=True)
        echo(
            _("{person}: {seconds} s of speech").format(
                person=person_id, seconds=centroids[label].seconds
            )
        )
    return save_directory(directory_file, raw)
