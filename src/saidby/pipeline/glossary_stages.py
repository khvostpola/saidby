# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
from typing import TYPE_CHECKING, Any

from saidby.engines.llm.llama_server import LlamaServerManager
from saidby.engines.llm.openai_compat import OpenAICompatClient, is_local_url
from saidby.errors import UsageError
from saidby.formats.audio import read_audio
from saidby.formats.corrections_log import read_corrections, write_corrections
from saidby.formats.words_json import read_transcript, write_transcript
from saidby.i18n import _, ngettext
from saidby.pipeline import cache
from saidby.pipeline.job import Recording, TextArtifact
from saidby.ports.corrector import LlmClient
from saidby.schema.telemetry import NOT_REQUESTED, NOTHING_TO_DO
from saidby.stages.correct import llm_correct
from saidby.stages.glossary.bias import Hotwords, build_hotwords
from saidby.stages.glossary.dialect import apply_dialect, dialect_map
from saidby.stages.glossary.prompts import PROMPT_VERSION
from saidby.stages.glossary.transplant import transplant, vocabulary
from saidby.stages.glossary.windows import find_windows, total_seconds
from saidby.telemetry.vram import VramPeak

if TYPE_CHECKING:
    from saidby.pipeline.runner import Pipeline


def _sha(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


class GlossaryStages:
    def __init__(self, pipeline: "Pipeline", llm: LlmClient | None = None) -> None:
        self.p = pipeline
        self.llm = llm
        self.llm_started = False
        self.hotwords_cache: Hotwords | None = None
        self.bias: dict[str, TextArtifact] = {}

    def preflight(self) -> None:
        settings = self.p.settings
        if not settings.correct:
            return
        if self.p._directory is None:
            raise UsageError(_("--correct needs --directory or --term with the terms to correct"))
        if settings.llm_url:
            if not is_local_url(settings.llm_url) and not settings.allow_remote_llm:
                raise UsageError(
                    _("the LLM endpoint is not on this machine; pass --allow-remote-llm to confirm")
                )
        elif self.llm is None:
            manager = self._manager()
            manager.check()
            self.llm = manager

    def _manager(self) -> LlamaServerManager:
        s = self.p.settings
        return LlamaServerManager(
            self.p.device, binary=s.llm_binary, model_key=s.llm_model, context=s.llm_context
        )

    def _client(self) -> LlmClient:
        if self.llm is None:
            url = self.p.settings.llm_url
            self.llm = (
                OpenAICompatClient(url, model_key=self.p.settings.llm_model)
                if url
                else self._manager()
            )
        if not self.llm_started:
            self.llm.start()
            self.llm_started = True
        return self.llm

    def release_llm(self) -> None:
        if self.llm is not None and self.llm_started:
            self.llm.stop()
            self.llm_started = False

    def hotwords(self) -> Hotwords:
        if self.hotwords_cache is None:
            directory = self.p._directory
            assert directory is not None
            engine = self.p._transcriber_engine()
            self.hotwords_cache = build_hotwords(directory, engine.count_tokens)
        return self.hotwords_cache

    def asr_bias(self, rec: Recording) -> dict[str, Any]:
        directory = self.p._directory
        if directory is None or not self.p.settings.bias:
            return {"skipped": NOT_REQUESTED}
        hot = self.hotwords()
        if not hot.text:
            return {"skipped": NOTHING_TO_DO}
        windows: list[tuple[float, float]] | None = None
        if self.p.settings.bias_mode == "windows":
            windows = find_windows(read_transcript(self.p.text[rec.slug].path), directory)
            rec.glossary.update(bias_windows=len(windows), bias_window_s=total_seconds(windows))
            if not windows:
                return {"skipped": NOTHING_TO_DO}
        engine = self.p._transcriber_engine()
        window_part = json.dumps(windows) if windows is not None else "full"
        key = cache.stage_key(
            "asr_bias",
            inputs={
                "audio": self.p._audio_sha[rec.slug],
                "hotwords": _sha(hot.text),
                "windows": _sha(window_part),
            },
            engine=engine.info,
            options={
                "language": self.p.settings.language,
                "deterministic": self.p.settings.deterministic,
            },
        )
        artifact = rec.work_dir / "transcript.bias.json"
        rec.glossary.update(
            bias_mode=self.p.settings.bias_mode,
            hotwords_tokens=hot.tokens,
            hotwords_truncated=hot.truncated,
        )
        if hot.truncated:
            rec.warnings.append(
                "glossary is larger than the hotword budget; some terms were left out"
            )
        self.bias[rec.slug] = TextArtifact(
            artifact, key, tuple(windows) if windows is not None else None
        )
        common: dict[str, Any] = {
            "engine": engine.info,
            "audio_s": rec.duration_s,
            "hotwords_tokens": hot.tokens,
            "hotwords_truncated": hot.truncated,
            "parts": [
                f"{engine.info.name} {engine.info.model}",
                ngettext("hotwords in {n} window", "hotwords in {n} windows", len(windows)).format(
                    n=len(windows)
                )
                if windows is not None
                else _("with hotwords"),
            ],
        }
        if windows is not None:
            common.update(bias_windows=len(windows), bias_window_s=total_seconds(windows))
        if cache.is_fresh(rec.work_dir, "asr_bias", key, [artifact]):
            return {**common, "cached": True}
        audio = read_audio(rec.wav)
        with VramPeak(self.p.device.kind == "cuda") as vram:
            load_s = self.p._load_once("asr", engine)
            transcript = engine.transcribe(
                audio, language=self.p.settings.language, hotwords=hot.text, clip_windows=windows
            )
        write_transcript(artifact, transcript)
        cache.write_marker(rec.work_dir, "asr_bias", key)
        return {
            **common,
            "model_load_s": load_s,
            "vram_peak_mb": vram.peak,
            "words": len(transcript.words()),
        }

    def transplant(self, rec: Recording) -> dict[str, Any]:
        directory = self.p._directory
        if directory is None:
            return {"skipped": NOT_REQUESTED}
        base = self.p.text[rec.slug]
        bias = self.bias.get(rec.slug) if self.p.settings.transplant else None
        mapping = dialect_map(directory)
        if bias is None and not mapping:
            return {"skipped": NOTHING_TO_DO}
        vocab = sorted(vocabulary(directory))
        key = cache.stage_key(
            "transplant",
            inputs={
                "text": base.key,
                "bias": bias.key if bias else "",
                "vocab": _sha(*vocab),
                "dialect": _sha(json.dumps(mapping, sort_keys=True)),
            },
        )
        artifact = rec.work_dir / "transcript.glossary.json"
        log_path = rec.work_dir / "corrections.glossary.jsonl"
        if not cache.is_fresh(rec.work_dir, "transplant", key, [artifact, log_path]):
            current = read_transcript(base.path)
            log = []
            if bias is not None:
                current, swaps = transplant(
                    current,
                    read_transcript(bias.path),
                    set(vocab),
                    list(bias.windows) if bias.windows is not None else None,
                )
                log += swaps
            current, dialect = apply_dialect(current, mapping)
            write_transcript(artifact, current)
            write_corrections(log_path, [*log, *dialect])
            cache.write_marker(rec.work_dir, "transplant", key)
            cached = False
        else:
            cached = True
        log = read_corrections(log_path)
        counts = {
            "transplant_swaps": sum(1 for c in log if c.by == "bias"),
            "dialect_swaps": sum(1 for c in log if c.by == "dialect"),
        }
        rec.glossary.update(counts)
        self.p.text[rec.slug] = TextArtifact(artifact, key)
        return {
            "cached": cached,
            **counts,
            "parts": ["word-level swaps", f"{sum(counts.values())} changes"],
        }

    def correct(self, rec: Recording) -> dict[str, Any]:
        directory = self.p._directory
        if directory is None or not self.p.settings.correct:
            return {"skipped": NOT_REQUESTED}
        base = self.p.text[rec.slug]
        settings = self.p.settings
        entries = _sha(directory.model_dump_json(exclude={"people": {"__all__": {"voiceprint"}}}))
        key = cache.stage_key(
            "correct",
            inputs={"text": base.key, "directory": entries},
            options={
                "chunk_words": settings.chunk_words,
                "prompt": PROMPT_VERSION,
                "language": settings.language,
                "llm": settings.llm_url or settings.llm_model,
            },
        )
        artifact = rec.work_dir / "transcript.corrected.json"
        log_path = rec.work_dir / "corrections.llm.jsonl"
        parts = ["llm", _("bounded corrections")]
        if cache.is_fresh(rec.work_dir, "correct", key, [artifact, log_path]):
            stats = (cache.read_marker(rec.work_dir, "correct") or {}).get("stats", {})
            self.p.text[rec.slug] = TextArtifact(artifact, key)
            rec.glossary["llm"] = {"enabled": True, **stats}
            return {"cached": True, **_llm_fields(stats), "parts": parts}
        client = self._client()
        with VramPeak(self.p.device.kind == "cuda") as vram:
            corrected, log, stats = llm_correct(
                read_transcript(base.path),
                directory,
                client,
                language=settings.language,
                chunk_words=settings.chunk_words,
            )
        write_transcript(artifact, corrected)
        write_corrections(log_path, log)
        record = {
            "chunks": stats.chunks,
            "accepted": stats.accepted,
            "rejected": stats.rejected,
            "truncated": stats.truncated,
        }
        cache.write_marker(rec.work_dir, "correct", key, stats=record)
        self.p.text[rec.slug] = TextArtifact(artifact, key)
        rec.glossary["llm"] = {
            "enabled": True,
            "engine": client.info.name,
            "model": client.info.model,
            **record,
        }
        return {
            "engine": client.info,
            "vram_peak_mb": vram.peak,
            **_llm_fields(record),
            "parts": [client.info.name, *parts[1:]],
        }


def _llm_fields(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "llm_chunks": stats.get("chunks"),
        "llm_accepted": stats.get("accepted"),
        "llm_rejected": stats.get("rejected"),
        "llm_truncated": stats.get("truncated"),
    }
