# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import shutil
from pathlib import Path

import pytest

from saidby.cli.progress import Progress
from saidby.config.settings import Settings
from saidby.engines.asr.fake import FakeTranscriber
from saidby.engines.diarize.fake import FakeDiarizer
from saidby.formats.manifest import read_manifest
from saidby.pipeline.runner import Pipeline

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/synthetic/tones_2spk_10s.flac"
RTTM = ROOT / "fixtures/synthetic/tones_2spk_10s.rttm"

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _run(tmp_path: Path, second: FakeDiarizer, **settings: object) -> Path:
    pipeline = Pipeline(
        Settings(device="cpu", language="es", compare="fake", **settings),  # type: ignore[arg-type]
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        compare_diarizer=second,
        progress=Progress("none"),
    )
    assert pipeline.run([FIXTURE], tmp_path)[0].status == "ok"
    return tmp_path / "tones_2spk_10s"


def test_agreeing_second_diarizer(tmp_path: Path) -> None:
    folder = _run(tmp_path, FakeDiarizer(rttm=RTTM))
    manifest = read_manifest(folder / "manifest.json")
    assert manifest.compare is not None
    assert manifest.compare["agreement"] == 1.0
    assert manifest.compare["disagreement_spans"] == []
    assert "compare" in [s.stage for s in manifest.stages]


def test_disagreeing_second_diarizer_is_recorded(tmp_path: Path) -> None:
    folder = _run(tmp_path, FakeDiarizer(turn_s=2.0, speakers=3), keep_intermediates=True)
    manifest = read_manifest(folder / "manifest.json")
    assert manifest.compare is not None
    assert manifest.compare["agreement"] < 0.9
    spans = manifest.compare["disagreement_spans"]
    assert spans
    assert all(0 <= s["start"] < s["end"] <= 10.5 for s in spans)
    events = [json.loads(x) for x in (folder / "logs/telemetry.jsonl").read_text().splitlines()]
    end = next(e for e in events if e["event"] == "stage.end" and e["stage"] == "compare")
    assert end["compare_engine"] == "fake"
    assert end["disagreement_spans"] == len(spans)
    assert (folder / ".work" / "compare.diarization.json").exists()


def test_without_flag_there_is_no_compare_stage(tmp_path: Path) -> None:
    pipeline = Pipeline(
        Settings(device="cpu", language="es"),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("none"),
    )
    pipeline.run([FIXTURE], tmp_path)
    manifest = read_manifest(tmp_path / "tones_2spk_10s/manifest.json")
    assert manifest.compare is None
    assert "compare" not in [s.stage for s in manifest.stages]
