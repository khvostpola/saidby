# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from typing import TYPE_CHECKING, Any

from saidby.formats.audio import read_audio
from saidby.pipeline import cache
from saidby.pipeline.job import Recording
from saidby.ports.diarizer import Diarizer
from saidby.ports.registry import make_diarizer
from saidby.schema.diarization import Diarization
from saidby.stages.compare import DEFAULT_MARGIN_S, compare_diarizations
from saidby.telemetry.vram import VramPeak

if TYPE_CHECKING:
    from saidby.pipeline.runner import Pipeline


class CompareStage:
    def __init__(self, pipeline: "Pipeline", engine: Diarizer | None = None) -> None:
        self.p = pipeline
        self.engine = engine
        self.results: dict[str, dict[str, Any]] = {}

    def _engine(self) -> Diarizer:
        if self.engine is None:
            name = self.p.settings.compare
            assert name is not None
            self.engine = make_diarizer(name, device=self.p.device)
        return self.engine

    def release(self) -> None:
        if self.engine is not None:
            self.engine.unload()
            self.p._loaded.discard("compare")

    def run(self, rec: Recording) -> dict[str, Any]:
        if not self.p.settings.compare:
            return {"skipped": True}
        engine = self._engine()
        diar_key = (cache.read_marker(rec.work_dir, "diarize") or {})["key"]
        key = cache.stage_key(
            "compare",
            inputs={"audio": self.p._audio_sha[rec.slug], "diarize": diar_key},
            engine=engine.info,
            options={"margin_s": DEFAULT_MARGIN_S},
        )
        artifact = rec.work_dir / "compare.json"
        base = Diarization.model_validate_json(
            (rec.work_dir / "diarization.json").read_text(encoding="utf-8")
        )
        cached = cache.is_fresh(rec.work_dir, "compare", key, [artifact])
        load_s = 0.0
        vram_peak = None
        if cached:
            record: dict[str, Any] = json.loads(artifact.read_text(encoding="utf-8"))
        else:
            audio = read_audio(rec.wav)
            with VramPeak(self.p.device.kind == "cuda") as vram:
                load_s = self.p._load_once("compare", engine)
                other = engine.diarize(
                    audio, uri=rec.slug, num_speakers=self.p.settings.num_speakers
                )
            vram_peak = vram.peak
            result = compare_diarizations(base, other, rec.duration_s)
            record = {
                "diarizer": engine.info.name,
                "margin_s": result.margin_s,
                "agreement": result.agreement,
                "disagreement_s": result.disagreement_s,
                "disagreement_spans": [{"start": s, "end": e} for s, e in result.spans],
            }
            artifact.write_text(json.dumps(record), encoding="utf-8")
            (rec.work_dir / "compare.diarization.json").write_text(
                other.model_dump_json(by_alias=True), encoding="utf-8"
            )
            cache.write_marker(rec.work_dir, "compare", key)
        self.results[rec.slug] = record
        return {
            "engine": engine.info,
            "cached": cached,
            "audio_s": rec.duration_s,
            "model_load_s": load_s or None,
            "vram_peak_mb": vram_peak,
            "compare_engine": engine.info.name,
            "agreement": record["agreement"],
            "disagreement_s": record["disagreement_s"],
            "disagreement_spans": len(record["disagreement_spans"]),
            "parts": [
                engine.info.name,
                f"agreement {record['agreement'] * 100:.1f}%",
                f"{len(record['disagreement_spans'])} spans differ",
            ],
        }
