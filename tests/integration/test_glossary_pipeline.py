# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from saidby.cli.progress import Progress
from saidby.config.settings import Settings
from saidby.engines.diarize.fake import FakeDiarizer
from saidby.engines.llm.fake import FakeLlmClient
from saidby.errors import UsageError
from saidby.formats.audio import SAMPLE_RATE
from saidby.formats.corrections_log import read_corrections
from saidby.formats.manifest import read_manifest
from saidby.formats.words_json import read_transcript
from saidby.pipeline.runner import Pipeline
from saidby.schema.engine import EngineInfo
from saidby.schema.transcript import Segment, Transcript, Word

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/synthetic/tones_2spk_10s.flac"
RTTM = ROOT / "fixtures/synthetic/tones_2spk_10s.rttm"

pytestmark = pytest.mark.needs_ffmpeg

PLAIN = "hola akme vamos parse con converse hoy"
BIASED = "hola Acme vamos parse con converse hoy"


class ScriptedTranscriber:
    def __init__(self) -> None:
        self.info = EngineInfo(kind="asr", name="scripted", model="scripted")
        self.hotwords_seen: list[str | None] = []
        self.windows_seen: list[list[tuple[float, float]] | None] = []
        self.loads = 0
        self.unloads = 0

    def load(self) -> float:
        self.loads += 1
        return 0.0

    def unload(self) -> None:
        self.unloads += 1

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def transcribe(
        self,
        audio: np.ndarray,
        *,
        language: str | None,
        hotwords: str | None = None,
        initial_prompt: str | None = None,
        clip_windows: list[tuple[float, float]] | None = None,
    ) -> Transcript:
        self.hotwords_seen.append(hotwords)
        self.windows_seen.append(clip_windows)
        words = [
            Word(start=i * 0.5 + 0.2, end=i * 0.5 + 0.6, word=f" {w}", p=0.9)
            for i, w in enumerate((BIASED if hotwords else PLAIN).split())
        ]
        if clip_windows:
            words = [w for w in words if any(s <= w.start < e for s, e in clip_windows)]
        return Transcript(
            language=language,
            duration_s=len(audio) / SAMPLE_RATE,
            engine=self.info,
            segments=[Segment(start=0.2, end=4.0, words=words)],
        )


def _directory(tmp_path: Path) -> Path:
    data = {
        "version": 1,
        "language": "es",
        "people": [{"id": "ana", "name": "Ana"}],
        "terms": [
            {"term": "Acme", "variants": ["akme"]},
            {"term": "Converge", "confusions": ["converse"]},
            {"term": "parce", "type": "dialect", "variants": ["parse"]},
        ],
    }
    path = tmp_path / "directory.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _llm(changes: list[dict[str, Any]]) -> FakeLlmClient:
    return FakeLlmClient(lambda system, user: {"changes": changes})


def _run(
    tmp_path: Path,
    transcriber: ScriptedTranscriber,
    directory: Path | None,
    llm: FakeLlmClient | None = None,
    **settings: Any,
) -> Path:
    pipeline = Pipeline(
        Settings(
            device="cpu", language="es", directory=[directory] if directory else [], **settings
        ),
        transcriber=transcriber,
        diarizer=FakeDiarizer(rttm=RTTM),
        llm=llm,
        progress=Progress("none"),
    )
    results = pipeline.run([FIXTURE], tmp_path / "out")
    assert results[0].status == "ok", results[0]
    return tmp_path / "out" / "tones_2spk_10s"


def _words(folder: Path) -> list[str]:
    return [w.word.strip() for w in read_transcript(folder / "transcript.words.json").words()]


def test_bias_pass_transplant_and_dialect(tmp_path: Path) -> None:
    transcriber = ScriptedTranscriber()
    folder = _run(tmp_path, transcriber, _directory(tmp_path))
    assert transcriber.hotwords_seen[0] is None
    assert transcriber.hotwords_seen[1] == "Ana Acme Converge parce"
    assert transcriber.loads == 1
    assert transcriber.unloads == 1
    assert _words(folder) == ["hola", "Acme", "vamos", "parce", "con", "converse", "hoy"]
    sources = {
        w.word.strip(): w.source for w in read_transcript(folder / "transcript.words.json").words()
    }
    assert sources["Acme"] == "bias"
    assert sources["parce"] == "dialect"
    log = read_corrections(folder / "corrections.jsonl")
    assert sorted(c.by for c in log) == ["bias", "dialect"]
    manifest = read_manifest(folder / "manifest.json")
    assert manifest.glossary is not None
    assert manifest.glossary["transplant_swaps"] == 1
    assert manifest.glossary["dialect_swaps"] == 1
    assert manifest.glossary["hotwords_tokens"] == 4
    stages = [s.stage for s in manifest.stages]
    assert stages[:4] == ["ingest", "asr", "asr_bias", "transplant"]
    assert "correct" not in stages


def test_no_bias_and_no_transplant_flags(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    t1 = ScriptedTranscriber()
    folder = _run(tmp_path / "a", t1, directory, bias=False)
    assert t1.hotwords_seen == [None]
    assert _words(folder)[1] == "akme"
    assert _words(folder)[3] == "parce"
    t2 = ScriptedTranscriber()
    folder = _run(tmp_path / "b", t2, directory, transplant=False)
    assert len(t2.hotwords_seen) == 2
    assert _words(folder)[1] == "akme"


def test_without_directory_nothing_glossary_related_runs(tmp_path: Path) -> None:
    transcriber = ScriptedTranscriber()
    folder = _run(tmp_path, transcriber, None)
    assert transcriber.hotwords_seen == [None]
    assert not (folder / "corrections.jsonl").exists()
    assert read_manifest(folder / "manifest.json").glossary is None


def test_llm_correction_runs_after_bias_and_logs(tmp_path: Path) -> None:
    llm = _llm([{"start": 5, "end": 5, "term": "Converge"}])
    folder = _run(tmp_path, ScriptedTranscriber(), _directory(tmp_path), llm, correct=True)
    assert _words(folder)[5] == "Converge"
    assert llm.started
    assert llm.stopped
    log = read_corrections(folder / "corrections.jsonl")
    assert [(c.by, c.status) for c in log if c.by == "llm"] == [("llm", "accepted")]
    manifest = read_manifest(folder / "manifest.json")
    assert manifest.glossary is not None
    assert manifest.glossary["llm"]["accepted"] == 1
    events = [
        json.loads(line)
        for line in (folder / "logs/telemetry.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    correct = next(e for e in events if e["event"] == "stage.end" and e["stage"] == "correct")
    assert correct["llm_accepted"] == 1
    assert "Converge" not in (folder / "logs/telemetry.jsonl").read_text(encoding="utf-8")
    assert "Converge" not in (folder / "logs/run.log").read_text(encoding="utf-8")


def test_correct_without_directory_is_a_usage_error(tmp_path: Path) -> None:
    pipeline = Pipeline(Settings(device="cpu", correct=True), progress=Progress("none"))
    with pytest.raises(UsageError):
        pipeline.run([FIXTURE], tmp_path)


def test_remote_llm_requires_explicit_permission(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    settings = Settings(
        device="cpu", correct=True, directory=[directory], llm_url="https://api.example.com"
    )
    with pytest.raises(UsageError, match="allow-remote-llm"):
        Pipeline(settings, progress=Progress("none")).run([FIXTURE], tmp_path)


def test_resume_reuses_glossary_stages(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    llm = _llm([{"start": 5, "end": 5, "term": "Converge"}])
    _run(tmp_path, ScriptedTranscriber(), directory, llm, correct=True, keep_intermediates=True)
    again = ScriptedTranscriber()
    llm2 = _llm([])
    folder = _run(tmp_path, again, directory, llm2, correct=True, keep_intermediates=True)
    assert again.hotwords_seen == []
    assert llm2.calls == []
    assert _words(folder)[5] == "Converge"


def test_windows_mode_biases_only_candidate_windows(tmp_path: Path) -> None:
    transcriber = ScriptedTranscriber()
    folder = _run(tmp_path, transcriber, _directory(tmp_path), bias_mode="windows")
    assert transcriber.windows_seen[0] is None
    windows = transcriber.windows_seen[1]
    assert windows
    assert all(end > start for start, end in windows)
    assert _words(folder)[1] == "Acme"
    manifest = read_manifest(folder / "manifest.json")
    assert manifest.glossary is not None
    assert manifest.glossary["bias_mode"] == "windows"
    assert manifest.glossary["bias_windows"] == len(windows)
    events = [
        json.loads(x)
        for x in (folder / "logs/telemetry.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    end = next(e for e in events if e["event"] == "stage.end" and e["stage"] == "asr_bias")
    assert end["bias_windows"] == len(windows)


def test_windows_mode_without_candidates_skips_second_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "saidby.pipeline.glossary_stages.find_windows", lambda transcript, directory: []
    )
    transcriber = ScriptedTranscriber()
    folder = _run(tmp_path, transcriber, _directory(tmp_path), bias_mode="windows")
    assert transcriber.hotwords_seen == [None]
    assert _words(folder)[1] == "akme"
    stages = [s.stage for s in read_manifest(folder / "manifest.json").stages]
    assert "asr_bias" not in stages


def test_extra_terms_alone_drive_the_bias_pass_and_the_transplant(tmp_path: Path) -> None:
    transcriber = ScriptedTranscriber()
    folder = _run(tmp_path, transcriber, None, terms=["Acme"])
    assert transcriber.hotwords_seen == [None, "Acme"]
    assert "Acme" in _words(folder)
    record = read_manifest(folder / "manifest.json").directory
    assert record == {"files": [], "people": 0, "terms": 1, "extra_terms": 1}


def test_extra_terms_join_the_directory_without_duplicating_its_terms(tmp_path: Path) -> None:
    transcriber = ScriptedTranscriber()
    folder = _run(tmp_path, transcriber, _directory(tmp_path), terms=["acme", "Rappi", "rappi"])
    assert transcriber.hotwords_seen[1] == "Ana Acme Converge Rappi parce"
    record = read_manifest(folder / "manifest.json").directory
    assert record is not None
    assert (record["terms"], record["extra_terms"]) == (4, 3)
    assert "directory.yaml" in Path(record["path"]).name
    assert "Rappi" not in (tmp_path / "directory.yaml").read_text(encoding="utf-8")
