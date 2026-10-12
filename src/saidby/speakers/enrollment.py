# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from saidby.config.settings import Settings
from saidby.errors import ConsentMissingError, InputError, UsageError
from saidby.formats.audio import read_audio
from saidby.formats.consent_yaml import append_consent, find_consent, load_consents
from saidby.formats.directory_yaml import save_directory
from saidby.formats.manifest import read_manifest
from saidby.formats.rttm import read_rttm
from saidby.formats.words_json import read_transcript
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


def resolve_consents(
    people: list[Person], consent_path: Path, provided: Mapping[str, ConsentInput]
) -> dict[str, ConsentRecord]:
    records, raw = load_consents(consent_path)
    resolved: dict[str, ConsentRecord] = {}
    for person in people:
        record = find_consent(records, person.id, person.name)
        given = provided.get(person.id)
        if record is None and given is not None:
            record = ConsentRecord(
                person=person.id,
                source=given.source,
                declared_by=given.declared_by,
                date=given.date or dt.date.today(),
            )
            append_consent(consent_path, raw, record)
        if record is None:
            raise ConsentMissingError(
                f"no voiceprint consent recorded for {person.id}; pass --consent-source and "
                f"--consent-declared-by or add it to {consent_path}"
            )
        resolved[person.id] = record
    return resolved


def _audio_files(out_dir: Path) -> tuple[Path | None, Path]:
    manifest = read_manifest(out_dir / "manifest.json")
    source = Path(manifest.source.path)
    kept = out_dir / ".work" / "audio.wav"
    if kept.exists():
        return kept, source
    if not source.is_file():
        raise InputError(
            f"original recording not found: {source}; run this from the folder where you ran "
            "saidby process, or run the process again with --keep-intermediates"
        )
    return None, source


def ensure_audio(out_dir: Path) -> None:
    _audio_files(out_dir)


def enroll_voices(
    out_dir: Path,
    assignments: list[tuple[str, str]],
    directory_file: Path,
    raw: Any,
    consents: Mapping[str, ConsentRecord],
    *,
    embedder_name: str,
    device: str,
    channel: str,
    echo: Callable[[str], None],
) -> Path | None:
    prepare(offline=True, want_cuda=device != "cpu")
    settings = Settings.load(overrides={"device": device})
    transcript = read_transcript(out_dir / "transcript.words.json")
    kept, source = _audio_files(out_dir)
    audio = read_audio(kept) if kept else ingest(source, out_dir / ".work").audio
    by_key = {key: s.label for s in transcript.speakers for key in (s.label, s.id) if key}
    spans: dict[str, list[tuple[float, float]]] = {}
    for turn in read_rttm(out_dir / "diarization.rttm"):
        label = by_key.get(turn.label)
        if label:
            spans.setdefault(label, []).append((turn.start, turn.end))
    embedder = make_embedder(embedder_name, device=resolve_device(settings.device))
    centroids = speaker_centroids(audio, spans, embedder)
    people = {p["id"]: p for p in raw["people"]}
    for label_arg, person_id in assignments:
        label = by_key.get(label_arg)
        if label is None or label not in centroids:
            known = sorted({s.label for s in transcript.speakers})
            raise UsageError(f"no usable speech for speaker {label_arg!r} (known: {known})")
        voiceprint = make_voiceprint(
            centroids[label], embedder, channel=channel, consent=consents[person_id]
        )
        people[person_id]["voiceprint"] = voiceprint.model_dump(mode="json", exclude_none=True)
        echo(f"{person_id}: {centroids[label].seconds} s of speech")
    return save_directory(directory_file, raw)
