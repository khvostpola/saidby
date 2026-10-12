# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import soundfile as sf

from saidby.errors import InputError, UsageError
from saidby.formats.manifest import read_manifest, write_manifest
from saidby.formats.rttm import read_rttm, write_rttm
from saidby.formats.transcripts import render_txt, render_vtt
from saidby.formats.words_json import read_transcript, write_transcript
from saidby.i18n import _
from saidby.schema.speakers import SpeakerEntry
from saidby.schema.transcript import Segment, Transcript, Word
from saidby.speakers.naming import track_path


class Folder:
    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        words = out_dir / "transcript.words.json"
        if not words.is_file():
            raise InputError(_("not a saidby output folder: {out_dir}").format(out_dir=out_dir))
        self.transcript = read_transcript(words)
        self.manifest = read_manifest(out_dir / "manifest.json")
        by_id = {s.file_id: s.label for s in self.transcript.speakers}
        self.turns = [
            t.model_copy(update={"label": by_id.get(t.label, t.label)})
            for t in read_rttm(out_dir / "diarization.rttm")
        ]

    def entry(self, label: str) -> SpeakerEntry:
        for s in self.transcript.speakers:
            if label in (s.label, s.id):
                return s
        known = ", ".join(s.label for s in self.transcript.speakers)
        raise UsageError(
            _("unknown speaker {label!r}; known: {known}").format(label=label, known=known)
        )

    def save(self, op: dict[str, str]) -> None:
        for s in self.transcript.speakers:
            s.track = track_path(s)
        write_transcript(self.out_dir / "transcript.words.json", self.transcript)
        (self.out_dir / "transcript.txt").write_text(render_txt(self.transcript), encoding="utf-8")
        (self.out_dir / "transcript.vtt").write_text(render_vtt(self.transcript), encoding="utf-8")
        ids = {s.label: s.file_id for s in self.transcript.speakers}
        write_rttm(
            self.out_dir / "diarization.rttm",
            self.out_dir.name,
            [t.model_copy(update={"label": ids.get(t.label, t.label)}) for t in self.turns],
        )
        files = dict(self.manifest.files)
        files["tracks"] = [s.track for s in self.transcript.speakers if s.track]
        if (self.out_dir / "corrections.jsonl").exists():
            files["corrections"] = "corrections.jsonl"
        manifest = self.manifest.model_copy(
            update={
                "speakers": self.transcript.speakers,
                "files": files,
                "edits": [*self.manifest.edits, {"at": datetime.now(UTC).isoformat(), **op}],
            }
        )
        write_manifest(self.out_dir / "manifest.json", manifest)


def show(out_dir: Path) -> list[dict[str, object]]:
    folder = Folder(out_dir)
    return [
        {
            "label": s.label,
            "id": s.id,
            "name": s.name,
            "identified": s.identified,
            "score": s.score,
            "speech_s": s.speech_s,
            "track": s.track,
            "merged_from": s.merged_from,
        }
        for s in folder.transcript.speakers
    ]


def map_speaker(out_dir: Path, label: str, person_id: str, name: str) -> None:
    folder = Folder(out_dir)
    entry = folder.entry(label)
    taken = {s.file_id for s in folder.transcript.speakers if s is not entry}
    if person_id in taken:
        raise UsageError(
            _("{person_id!r} is already used by another speaker; use merge instead").format(
                person_id=person_id
            )
        )
    old_track = out_dir / track_path(entry)
    entry.id, entry.name, entry.identified, entry.score = person_id, name, False, None
    new_track = out_dir / track_path(entry)
    if old_track.exists() and old_track != new_track:
        old_track.rename(new_track)
    folder.save({"op": "map", "label": entry.label, "id": person_id, "name": name})


def _rebuild_words(transcript: Transcript, source: str, target: str) -> Transcript:
    segments = [
        Segment(
            start=seg.start,
            end=seg.end,
            words=[
                Word(**{**w.model_dump(), "speaker": target if w.speaker == source else w.speaker})
                for w in seg.words
            ],
        )
        for seg in transcript.segments
    ]
    return transcript.model_copy(update={"segments": segments})


def merge_speakers(out_dir: Path, labels: list[str], into: str) -> None:
    folder = Folder(out_dir)
    target = folder.entry(into)
    sources = [folder.entry(label) for label in labels]
    if any(s is target for s in sources):
        raise UsageError(_("cannot merge a speaker into itself"))
    target_audio_path = out_dir / track_path(target)
    mixed: np.ndarray | None = None
    rate = 16000
    if target_audio_path.exists():
        mixed, rate = sf.read(target_audio_path, dtype="float32")
    for source in sources:
        src_path = out_dir / track_path(source)
        if src_path.exists():
            data, rate = sf.read(src_path, dtype="float32")
            mixed = data if mixed is None else np.where(mixed != 0, mixed, data)
            src_path.unlink()
        folder.transcript = _rebuild_words(folder.transcript, source.label, target.label)
        folder.turns = [
            t.model_copy(update={"label": target.label}) if t.label == source.label else t
            for t in folder.turns
        ]
        target.speech_s = round(target.speech_s + source.speech_s, 3)
        target.merged_from = [*target.merged_from, source.label, *source.merged_from]
    removed = {s.label for s in sources}
    folder.transcript = folder.transcript.model_copy(
        update={"speakers": [s for s in folder.transcript.speakers if s.label not in removed]}
    )
    if mixed is not None:
        sf.write(target_audio_path, mixed, rate, format="FLAC", subtype="PCM_16")
    folder.save({"op": "merge", "label": ",".join(sorted(removed)), "into": target.label})
