# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import platform
import shutil
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from saidby import __version__
from saidby.cli.progress import Progress, fmt_clock
from saidby.config.settings import Settings
from saidby.errors import InputError, SaidbyError, StageError
from saidby.formats.audio import SAMPLE_RATE, read_audio
from saidby.formats.manifest import read_manifest, write_manifest
from saidby.formats.rttm import write_rttm
from saidby.formats.transcripts import render_txt, render_vtt
from saidby.formats.words_json import read_transcript, write_transcript
from saidby.pipeline import cache
from saidby.pipeline.job import Recording, RecordingResult
from saidby.ports.diarizer import Diarizer
from saidby.ports.registry import make_diarizer, make_transcriber
from saidby.ports.transcriber import Transcriber
from saidby.runtime import prepare
from saidby.runtime.device import DeviceInfo, resolve_device
from saidby.runtime.netguard import guard_network
from saidby.schema.diarization import Diarization
from saidby.schema.ids import unique_slugs
from saidby.schema.manifest import AudioInfo, DeviceRecord, Manifest, SourceInfo, StageRecord
from saidby.schema.telemetry import StageName
from saidby.stages.align import assign_speakers
from saidby.stages.ingest import file_sha256, ingest
from saidby.stages.tracks import render_track
from saidby.telemetry.runlog import RunLog
from saidby.telemetry.sink import TelemetrySink
from saidby.telemetry.vram import VramPeak

if TYPE_CHECKING:
    from saidby.schema.engine import EngineInfo
    from saidby.schema.speakers import SpeakerEntry

STAGES: tuple[StageName, ...] = ("ingest", "asr", "diarize", "align", "tracks", "outputs")


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        *,
        transcriber: Transcriber | None = None,
        diarizer: Diarizer | None = None,
        progress: Progress | None = None,
    ) -> None:
        self.settings = settings
        self.progress = progress or Progress("none")
        self._transcriber = transcriber
        self._diarizer = diarizer
        self.run_id = str(uuid.uuid4())
        self.device: DeviceInfo = DeviceInfo("cpu")
        self.warnings: list[str] = []
        self._audio_sha: dict[str, str] = {}
        self._speakers: dict[str, list[SpeakerEntry]] = {}
        self._loaded: set[str] = set()

    def run(self, inputs: list[Path], out_root: Path) -> list[RecordingResult]:
        self.device = resolve_device(self.settings.device)
        prepare(offline=True, want_cuda=self.device.kind == "cuda")
        if self.settings.strict_offline:
            with guard_network():
                return self._run(inputs, out_root)
        return self._run(inputs, out_root)

    def _recordings(self, inputs: list[Path], out_root: Path) -> list[Recording]:
        slugs = unique_slugs([p.stem for p in inputs])
        recs = []
        for i, (media, slug) in enumerate(zip(inputs, slugs, strict=True), 1):
            out_dir = out_root / slug
            (out_dir / ".work").mkdir(parents=True, exist_ok=True)
            recs.append(
                Recording(
                    index=i,
                    media=media,
                    slug=slug,
                    out_dir=out_dir,
                    log=RunLog(out_dir / "logs" / "run.log"),
                    telemetry=TelemetrySink(out_dir / "logs" / "telemetry.jsonl", self.run_id),
                    created_at=datetime.now(UTC),
                )
            )
        return recs

    def _run(self, inputs: list[Path], out_root: Path) -> list[RecordingResult]:
        recs = self._recordings(inputs, out_root)
        total = len(recs)
        for rec in recs:
            rec.telemetry.emit(
                "run.start",
                files_total=total,
                python=platform.python_version(),
                platform=platform.system().lower(),
            )
            rec.telemetry.emit("file.start", file_index=rec.index, files_total=total)
        try:
            handlers: dict[StageName, Callable[[Recording], dict[str, Any]]] = {
                "ingest": self._ingest,
                "asr": self._asr,
                "diarize": self._diarize,
                "align": self._align,
                "tracks": self._tracks,
                "outputs": self._outputs,
            }
            for stage in STAGES:
                for rec in recs:
                    if rec.alive:
                        self._run_stage(rec, stage, handlers[stage], total)
                        if not rec.alive and self.settings.fail_fast:
                            break
                if stage == "asr" and self._transcriber is not None:
                    self._transcriber.unload()
                    self._loaded.discard("asr")
                if stage == "diarize" and self._diarizer is not None:
                    self._diarizer.unload()
                    self._loaded.discard("diarize")
                if self.settings.fail_fast and any(not r.alive for r in recs):
                    break
        except KeyboardInterrupt:
            for rec in recs:
                if rec.alive:
                    rec.status = "interrupted"
                    self._finalize(rec, total)
            raise
        return [self._finalize(rec, total) for rec in recs]

    def _run_stage(
        self,
        rec: Recording,
        stage: StageName,
        handler: Callable[[Recording], dict[str, Any]],
        total: int,
    ) -> None:
        telemetry_stage = stage
        rec.telemetry.emit("stage.start", stage=telemetry_stage, file_index=rec.index)
        started = time.perf_counter()
        try:
            info = handler(rec)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            rec.status = "failed"
            rec.failed_stage = stage
            rec.error_type = type(exc).__name__
            rec.error = str(exc)
            rec.exit_code = exc.exit_code if isinstance(exc, SaidbyError) else StageError.exit_code
            rec.log.fail(stage, f"{rec.error_type}: {exc}")
            rec.telemetry.emit(
                "stage.error",
                stage=telemetry_stage,
                error_type=rec.error_type,
                exit_code=rec.exit_code,
            )
            rec.stages.append(StageRecord(stage=telemetry_stage, status="failed"))
            self.progress.stage_error(
                index=rec.index, total=total, slug=rec.slug, stage=stage, error_type=rec.error_type
            )
            return
        wall = round(time.perf_counter() - started, 3)
        engine: EngineInfo | None = info.pop("engine", None)
        cached = bool(info.pop("cached", False))
        parts = info.pop("parts", [])
        fields = {
            k: v
            for k, v in info.items()
            if k
            in {
                "audio_s",
                "model_load_s",
                "vram_peak_mb",
                "segments",
                "words",
                "speakers",
                "turns",
                "speech_s",
                "overlap_s",
                "mode",
            }
        }
        audio_s = fields.get("audio_s")
        rtf = (
            round(wall / audio_s, 4)
            if audio_s and not cached and stage in {"asr", "diarize"}
            else None
        )
        event: dict[str, Any] = dict(fields)
        if engine is not None:
            event.update(
                engine=engine.name,
                model=engine.model,
                device=engine.device,
                compute_type=engine.compute_type,
            )
            if engine.revision:
                event["revision"] = engine.revision
        rec.telemetry.emit(
            "stage.skip" if cached else "stage.end",
            stage=telemetry_stage,
            file_index=rec.index,
            wall_s=wall,
            rtf=rtf,
            cached=cached,
            **event,
        )
        rec.stages.append(
            StageRecord(stage=telemetry_stage, engine=engine, wall_s=wall, cached=cached)
        )
        rec.log.note(stage, "cached" if cached else f"done in {wall}s")
        self.progress.stage_end(
            index=rec.index,
            total=total,
            slug=rec.slug,
            stage=stage,
            parts=parts,
            wall_s=wall,
            rtf=rtf,
            cached=cached,
        )

    def _ingest(self, rec: Recording) -> dict[str, Any]:
        if not rec.media.is_file():
            raise InputError(f"input file not found: {rec.media}")
        rec.source_sha256 = file_sha256(rec.media)
        rec.size_bytes = rec.media.stat().st_size
        previous = rec.out_dir / "manifest.json"
        if previous.is_file() and not self.settings.force:
            try:
                old = read_manifest(previous)
            except ValueError:
                old = None
            if old is not None and old.source.sha256 != rec.source_sha256:
                raise InputError(
                    "output folder holds results for a different input; use --force to overwrite"
                )
        key = cache.stage_key("ingest", inputs={"source": rec.source_sha256})
        marker_extra: dict[str, Any]
        if cache.is_fresh(rec.work_dir, "ingest", key, [rec.wav]):
            marker = cache.read_marker(rec.work_dir, "ingest") or {}
            rec.duration_s = float(marker["duration_s"])
            self._audio_sha[rec.slug] = str(marker["audio_sha256"])
            return {
                "cached": True,
                "audio_s": rec.duration_s,
                "parts": [f"{fmt_clock(rec.duration_s)} of audio"],
            }
        result = ingest(rec.media, rec.work_dir)
        rec.duration_s = result.duration_s
        self._audio_sha[rec.slug] = file_sha256(rec.wav)
        marker_extra = {"duration_s": rec.duration_s, "audio_sha256": self._audio_sha[rec.slug]}
        cache.write_marker(rec.work_dir, "ingest", key, **marker_extra)
        return {
            "audio_s": rec.duration_s,
            "parts": ["ffmpeg", f"{fmt_clock(rec.duration_s)} of audio"],
        }

    def _load_once(self, name: str, engine: Transcriber | Diarizer) -> float:
        if name in self._loaded:
            return 0.0
        self._loaded.add(name)
        return engine.load()

    def _transcriber_engine(self) -> Transcriber:
        if self._transcriber is None:
            self._transcriber = make_transcriber(
                self.settings.asr_engine,
                model=self.settings.asr_model,
                device=self.device,
                compute_type=self.settings.compute_type,
            )
        return self._transcriber

    def _asr(self, rec: Recording) -> dict[str, Any]:
        engine = self._transcriber_engine()
        key = cache.stage_key(
            "asr",
            inputs={"audio": self._audio_sha[rec.slug]},
            engine=engine.info,
            options={"language": self.settings.language},
        )
        artifact = rec.work_dir / "transcript.asr.json"
        parts = [engine.info.name, engine.info.model, engine.info.device or "cpu"]
        if cache.is_fresh(rec.work_dir, "asr", key, [artifact]):
            transcript = read_transcript(artifact)
            return {
                "cached": True,
                "engine": engine.info,
                "audio_s": rec.duration_s,
                "segments": len(transcript.segments),
                "words": len(transcript.words()),
                "parts": parts,
            }
        audio = read_audio(rec.wav)
        with VramPeak(self.device.kind == "cuda") as vram:
            load_s = engine.load() if not getattr(engine, "_loaded_once", False) else 0.0
            engine._loaded_once = True  # type: ignore[attr-defined]
            transcript = engine.transcribe(audio, language=self.settings.language)
        write_transcript(artifact, transcript)
        cache.write_marker(rec.work_dir, "asr", key)
        if transcript.language and not self.settings.language:
            rec.log.note("asr", f"detected language {transcript.language}")
        return {
            "engine": engine.info,
            "audio_s": rec.duration_s,
            "model_load_s": load_s,
            "vram_peak_mb": vram.peak,
            "segments": len(transcript.segments),
            "words": len(transcript.words()),
            "parts": [*parts, f"{fmt_clock(rec.duration_s)} of audio"],
        }

    def _diarizer_engine(self) -> Diarizer:
        if self._diarizer is None:
            self._diarizer = make_diarizer(self.settings.diarizer, device=self.device)
        return self._diarizer

    def _diarize(self, rec: Recording) -> dict[str, Any]:
        engine = self._diarizer_engine()
        key = cache.stage_key(
            "diarize",
            inputs={"audio": self._audio_sha[rec.slug]},
            engine=engine.info,
            options={"num_speakers": self.settings.num_speakers},
        )
        artifact = rec.work_dir / "diarization.json"
        parts = [engine.info.name, engine.info.device or "cpu"]
        if cache.is_fresh(rec.work_dir, "diarize", key, [artifact]):
            diar = Diarization.model_validate_json(artifact.read_text(encoding="utf-8"))
            return {
                "cached": True,
                "engine": engine.info,
                "audio_s": rec.duration_s,
                "speakers": len(diar.labels()),
                "turns": len(diar.turns),
                "parts": parts,
            }
        audio = read_audio(rec.wav)
        with VramPeak(self.device.kind == "cuda") as vram:
            load_s = engine.load() if not getattr(engine, "_loaded_once", False) else 0.0
            engine._loaded_once = True  # type: ignore[attr-defined]
            diar = engine.diarize(audio, uri=rec.slug, num_speakers=self.settings.num_speakers)
        artifact.write_text(diar.model_dump_json(by_alias=True), encoding="utf-8")
        cache.write_marker(rec.work_dir, "diarize", key)
        mode = getattr(engine, "mode", None)
        return {
            "engine": engine.info,
            "audio_s": rec.duration_s,
            "model_load_s": load_s,
            "vram_peak_mb": vram.peak,
            "speakers": len(diar.labels()),
            "turns": len(diar.turns),
            "speech_s": round(diar.speech_s(), 1),
            "overlap_s": round(diar.overlap_s(), 1),
            "mode": mode,
            "parts": [*parts, f"{len(diar.labels())} speakers"],
        }

    def _align(self, rec: Recording) -> dict[str, Any]:
        asr_key = (cache.read_marker(rec.work_dir, "asr") or {})["key"]
        diar_key = (cache.read_marker(rec.work_dir, "diarize") or {})["key"]
        key = cache.stage_key("align", inputs={"asr": asr_key, "diarize": diar_key})
        artifact = rec.work_dir / "transcript.aligned.json"
        if cache.is_fresh(rec.work_dir, "align", key, [artifact]):
            aligned = read_transcript(artifact)
            return {
                "cached": True,
                "words": len(aligned.words()),
                "speakers": len(aligned.speakers),
                "parts": ["word-to-speaker"],
            }
        transcript = read_transcript(rec.work_dir / "transcript.asr.json")
        diar = Diarization.model_validate_json(
            (rec.work_dir / "diarization.json").read_text(encoding="utf-8")
        )
        aligned = assign_speakers(transcript, diar)
        write_transcript(artifact, aligned)
        cache.write_marker(rec.work_dir, "align", key)
        unassigned = sum(1 for w in aligned.words() if w.speaker is None)
        if unassigned:
            rec.warnings.append(f"{unassigned} words could not be assigned to a speaker")
            rec.log.caution("align", f"{unassigned} words without speaker")
        return {
            "words": len(aligned.words()),
            "speakers": len(aligned.speakers),
            "parts": ["word-to-speaker", f"{len(aligned.speakers)} speakers"],
        }

    def _tracks(self, rec: Recording) -> dict[str, Any]:
        align_key = (cache.read_marker(rec.work_dir, "align") or {})["key"]
        key = cache.stage_key(
            "tracks", inputs={"align": align_key, "audio": self._audio_sha[rec.slug]}
        )
        listing = rec.work_dir / "tracks.json"
        aligned = read_transcript(rec.work_dir / "transcript.aligned.json")
        files = {s.label: f"speakers/{s.file_id}.flac" for s in aligned.speakers}
        fresh = cache.is_fresh(rec.work_dir, "tracks", key, [listing])
        if fresh and all((rec.out_dir / rel).exists() for rel in files.values()):
            return {"cached": True, "speakers": len(files), "parts": [f"{len(files)} tracks"]}
        diar = Diarization.model_validate_json(
            (rec.work_dir / "diarization.json").read_text(encoding="utf-8")
        )
        audio = read_audio(rec.wav)
        for label, rel in files.items():
            render_track(rec.out_dir / rel, audio, [t for t in diar.turns if t.label == label])
        listing.write_text(json.dumps(files), encoding="utf-8")
        cache.write_marker(rec.work_dir, "tracks", key)
        return {"speakers": len(files), "parts": [f"{len(files)} tracks", "aligned FLAC"]}

    def _outputs(self, rec: Recording) -> dict[str, Any]:
        aligned = read_transcript(rec.work_dir / "transcript.aligned.json")
        diar = Diarization.model_validate_json(
            (rec.work_dir / "diarization.json").read_text(encoding="utf-8")
        )
        tracks: dict[str, str] = json.loads(
            (rec.work_dir / "tracks.json").read_text(encoding="utf-8")
        )
        speakers = [s.model_copy(update={"track": tracks.get(s.label)}) for s in aligned.speakers]
        final = aligned.model_copy(update={"speakers": speakers})
        write_transcript(rec.out_dir / "transcript.words.json", final)
        (rec.out_dir / "transcript.txt").write_text(render_txt(final), encoding="utf-8")
        (rec.out_dir / "transcript.vtt").write_text(render_vtt(final), encoding="utf-8")
        ids = {s.label: s.file_id for s in speakers}
        write_rttm(
            rec.out_dir / "diarization.rttm",
            rec.slug,
            [t.model_copy(update={"label": ids.get(t.label, t.label)}) for t in diar.turns],
        )
        self._speakers[rec.slug] = speakers
        return {"parts": ["txt", "vtt", "words.json", "rttm"], "speakers": len(speakers)}

    def _finalize(self, rec: Recording, total: int) -> RecordingResult:
        speakers = self._speakers.get(rec.slug, [])
        manifest = Manifest(
            tool={"name": "saidby", "version": __version__},
            run_id=self.run_id,
            status=rec.status,
            created_at=rec.created_at or datetime.now(UTC),
            finished_at=datetime.now(UTC),
            source=SourceInfo(
                path=str(rec.media),
                sha256=rec.source_sha256,
                size_bytes=rec.size_bytes,
                duration_s=round(rec.duration_s, 3),
            ),
            audio=AudioInfo(
                sample_rate=SAMPLE_RATE, channels=1, duration_s=round(rec.duration_s, 3)
            ),
            language=self.settings.language,
            device=DeviceRecord(
                requested=self.settings.device,
                used=self.device.kind,
                name=self.device.name,
                vram_total_mb=self.device.vram_total_mb,
            ),
            stages=rec.stages,
            speakers=speakers,
            files={
                "transcript_txt": "transcript.txt",
                "transcript_vtt": "transcript.vtt",
                "words": "transcript.words.json",
                "rttm": "diarization.rttm",
                "tracks": [s.track for s in speakers if s.track],
                "run_log": "logs/run.log",
                "telemetry": "logs/telemetry.jsonl",
            },
            warnings=rec.warnings,
            failed_stage=rec.failed_stage,
            error_type=rec.error_type,
            error=rec.error,
        )
        write_manifest(rec.out_dir / "manifest.json", manifest)
        rec.telemetry.emit(
            "file.end",
            file_index=rec.index,
            files_total=total,
            status=rec.status,
            audio_s=round(rec.duration_s, 2),
        )
        rec.telemetry.emit("run.end", status=rec.status)
        if rec.status == "ok" and not self.settings.keep_intermediates:
            shutil.rmtree(rec.work_dir, ignore_errors=True)
        detail = (
            f"{len(speakers)} speakers"
            if rec.status == "ok"
            else f"{rec.failed_stage}: {rec.error_type}"
        )
        self.progress.file_end(
            index=rec.index,
            total=total,
            slug=rec.slug,
            status="done" if rec.status == "ok" else rec.status,
            out=str(rec.out_dir),
            detail=detail,
        )
        return RecordingResult(rec.slug, rec.out_dir, rec.status, rec.exit_code, rec.error_type)
