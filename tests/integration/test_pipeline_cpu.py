# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from saidby.cli.progress import Progress
from saidby.config.settings import Settings
from saidby.engines.asr.fake import FakeTranscriber
from saidby.engines.diarize.fake import FakeDiarizer
from saidby.formats.manifest import read_manifest
from saidby.formats.words_json import read_transcript
from saidby.pipeline.runner import Pipeline

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/synthetic/tones_2spk_10s.flac"
RTTM = ROOT / "fixtures/synthetic/tones_2spk_10s.rttm"

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _pipeline(**kwargs: object) -> Pipeline:
    settings = Settings(device="cpu", language="es", **kwargs)  # type: ignore[arg-type]
    return Pipeline(
        settings,
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("none"),
    )


def test_end_to_end_with_fakes(tmp_path: Path) -> None:
    results = _pipeline().run([FIXTURE], tmp_path)
    assert [r.status for r in results] == ["ok"]
    out = tmp_path / "tones_2spk_10s"
    manifest = read_manifest(out / "manifest.json")
    assert manifest.status == "ok"
    assert [s.stage for s in manifest.stages] == [
        "ingest",
        "asr",
        "diarize",
        "align",
        "tracks",
        "outputs",
    ]
    transcript = read_transcript(out / "transcript.words.json")
    assert transcript.words()
    assert {s.label for s in transcript.speakers} == {"SPEAKER_00", "SPEAKER_01"}
    assert (out / "transcript.vtt").read_text().startswith("WEBVTT")
    assert "SPEAKER_00" in (out / "transcript.txt").read_text()
    assert (out / "diarization.rttm").read_text().count("SPEAKER") >= 4
    source, _ = sf.read(FIXTURE)
    for track in (out / "speakers").glob("*.flac"):
        data, _ = sf.read(track)
        assert len(data) == len(source)
    assert not (out / ".work").exists()


def test_telemetry_is_valid_and_has_no_text(tmp_path: Path) -> None:
    _pipeline().run([FIXTURE], tmp_path)
    lines = (tmp_path / "tones_2spk_10s/logs/telemetry.jsonl").read_text().splitlines()
    events = [json.loads(line) for line in lines]
    names = [e["event"] for e in events]
    assert names[0] == "run.start"
    assert "stage.end" in names
    assert not any(
        "word" in json.dumps(e) for e in events if e["event"] == "stage.end" and "text" in e
    )
    run_log = (tmp_path / "tones_2spk_10s/logs/run.log").read_text()
    assert "asr:" in run_log
    assert "word0" not in run_log


def test_resume_skips_cached_stages(tmp_path: Path) -> None:
    _pipeline(keep_intermediates=True).run([FIXTURE], tmp_path)
    out = tmp_path / "tones_2spk_10s"
    (out / ".work" / "stage.diarize.json").unlink()
    _pipeline(keep_intermediates=True).run([FIXTURE], tmp_path)
    events = [json.loads(line) for line in (out / "logs/telemetry.jsonl").read_text().splitlines()]
    second_run = events[len(events) // 2 :]
    skipped = {e["stage"] for e in second_run if e["event"] == "stage.skip"}
    assert {"ingest", "asr"} <= skipped
    assert "diarize" not in skipped


def test_failure_keeps_work_and_reports(tmp_path: Path) -> None:
    broken = tmp_path / "broken.wav"
    broken.write_bytes(b"not audio")
    results = _pipeline().run([broken], tmp_path / "out")
    assert results[0].status == "failed"
    assert results[0].exit_code == 3
    manifest = read_manifest(tmp_path / "out/broken/manifest.json")
    assert manifest.failed_stage == "ingest"
    assert (tmp_path / "out/broken/.work").exists()


def test_multi_file_slugs_and_collisions(tmp_path: Path) -> None:
    a, b = tmp_path / "a" / "call.flac", tmp_path / "b" / "call.flac"
    for p in (a, b):
        p.parent.mkdir()
        shutil.copy(FIXTURE, p)
    results = _pipeline().run([a, b], tmp_path / "out")
    assert [r.slug for r in results] == ["call", "call-2"]
    assert all(r.status == "ok" for r in results)


def test_different_input_in_same_folder_is_refused(tmp_path: Path) -> None:
    _pipeline().run([FIXTURE], tmp_path)
    other = tmp_path / "tones_2spk_10s.wav"
    sf.write(other, np.zeros(16000, dtype=np.float32), 16000)
    results = _pipeline().run([other], tmp_path)
    assert results[0].status == "failed"
    assert results[0].exit_code == 3


@pytest.mark.enable_socket
def test_strict_offline_run_opens_no_connections(tmp_path: Path) -> None:
    from saidby.runtime.netguard import guard_network

    settings = Settings(device="cpu", language="es", strict_offline=True)
    pipeline = Pipeline(
        settings,
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("none"),
    )
    with guard_network(raise_on_attempt=False) as guard:
        results = pipeline.run([FIXTURE], tmp_path)
    assert results[0].status == "ok"
    assert guard.events == []


def test_device_fallback_note_reaches_the_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from saidby.pipeline import runner as runner_module
    from saidby.runtime.device import DeviceInfo

    monkeypatch.setattr(
        runner_module,
        "resolve_device",
        lambda requested: DeviceInfo("cpu", note="running on CPU: test"),
    )
    _pipeline().run([FIXTURE], tmp_path)
    manifest = read_manifest(tmp_path / "tones_2spk_10s/manifest.json")
    assert manifest.warnings == ["running on CPU: test"]
    assert manifest.device.used == "cpu"


def test_run_ends_with_a_summary_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pipeline = Pipeline(
        Settings(device="cpu", language="es"),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("human"),
    )
    pipeline.run([FIXTURE], tmp_path)
    last = capsys.readouterr().err.strip().splitlines()[-1]
    assert last.startswith("[total]")
    assert "started" in last
    assert "finished" in last
    assert "0:10 of audio" in last


def test_json_progress_announces_the_run_and_the_device_before_any_stage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pipeline = Pipeline(
        Settings(device="cpu", language="es"),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("json"),
    )
    pipeline.run([FIXTURE], tmp_path)
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    names = [e["event"] for e in events]
    assert names[:3] == ["run.start", "device", "stage.start"]
    assert names[-1] == "run.end"
    device = events[1]
    assert (device["requested"], device["used"], device["reason"]) == (
        "cpu",
        "cpu",
        "requested_cpu",
    )


def test_human_progress_prints_the_device_line_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pipeline = Pipeline(
        Settings(device="cpu", language="es"),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("human"),
    )
    pipeline.run([FIXTURE], tmp_path)
    lines = capsys.readouterr().err.strip().splitlines()
    assert lines[0].startswith("device")
    assert lines[0].endswith("(--device cpu)")
    assert lines[1].startswith("[1/1] ingest")


def test_json_progress_announces_each_model_load_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pipeline = Pipeline(
        Settings(device="cpu", language="es"),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("json"),
    )
    pipeline.run([FIXTURE, FIXTURE.with_name("tones_2spk_10s.flac")], tmp_path)
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    loads = [(e["stage"], e["model"]) for e in events if e["event"] == "stage.loading"]
    assert loads == [("asr", "fake"), ("diarize", "fake")]
    asr = [e["event"] for e in events if e.get("stage") == "asr"]
    assert asr[:3] == ["stage.start", "stage.loading", "stage.end"]
