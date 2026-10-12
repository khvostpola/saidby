# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import soundfile as sf
import yaml
from typer.testing import CliRunner

from saidby.cli import app
from saidby.cli.progress import Progress
from saidby.config.settings import Settings
from saidby.engines.asr.fake import FakeTranscriber
from saidby.engines.diarize.fake import FakeDiarizer
from saidby.engines.embed.fake import FakeEmbedder, vector_for
from saidby.formats.directory_yaml import encode_vector
from saidby.formats.manifest import read_manifest
from saidby.formats.rttm import read_rttm
from saidby.formats.words_json import read_transcript
from saidby.pipeline.runner import Pipeline
from saidby.runtime.device_cache import read_cache

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/synthetic/tones_2spk_10s.flac"
RTTM = ROOT / "fixtures/synthetic/tones_2spk_10s.rttm"
VOICES = {(0.0, 3.3): "alice", (3.3, 6.2): "bob", (6.2, 8.4): "alice", (8.4, 10.0): "bob"}
runner = CliRunner()

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _voiceprint(name: str) -> dict[str, Any]:
    return {
        "model": "fake",
        "revision": "0" * 40,
        "dim": 16,
        "sample_rate": 16000,
        "preprocessing": "fake;v1",
        "channel": "phone",
        "seconds": 60.0,
        "vector": encode_vector(vector_for(name)),
    }


def _directory(tmp_path: Path, enrolled: bool = True) -> Path:
    people: list[dict[str, Any]] = [
        {"id": "alice", "name": "Alice"},
        {"id": "bob", "name": "Bob"},
    ]
    if enrolled:
        for p in people:
            p["voiceprint"] = _voiceprint(str(p["id"]))
    path = tmp_path / "directory.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "language": "es", "people": people}))
    if enrolled:
        records = [
            {
                "person": p["id"],
                "source": "signed form",
                "declared_by": p["name"],
                "date": "2026-10-11",
            }
            for p in people
        ]
        (tmp_path / "consent.yaml").write_text(yaml.safe_dump(records))
    return path


def _run(tmp_path: Path, directory: Path | None, **settings: object) -> Path:
    pipeline = Pipeline(
        Settings(
            device="cpu",
            language="es",
            directory=[directory] if directory else [],
            **settings,  # type: ignore[arg-type]
        ),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        embedder=FakeEmbedder(VOICES),
        progress=Progress("none"),
    )
    out = tmp_path / "out"
    assert pipeline.run([FIXTURE], out)[0].status == "ok"
    return out / "tones_2spk_10s"


def test_identification_names_speakers_and_tracks(tmp_path: Path) -> None:
    folder = _run(tmp_path, _directory(tmp_path))
    transcript = read_transcript(folder / "transcript.words.json")
    names = {s.label: s.name for s in transcript.speakers}
    assert names == {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
    assert all(s.identified for s in transcript.speakers)
    assert (folder / "speakers/alice.flac").exists()
    assert "Alice:" in (folder / "transcript.txt").read_text()
    assert "<v Bob>" in (folder / "transcript.vtt").read_text()
    assert {t.label for t in read_rttm(folder / "diarization.rttm")} == {"alice", "bob"}
    manifest = read_manifest(folder / "manifest.json")
    assert manifest.directory is not None
    assert manifest.directory["people"] == 2
    assert "identify" in [s.stage for s in manifest.stages]


def test_no_identify_flag_and_unenrolled_directory(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    off = _run(tmp_path / "a", _directory(tmp_path / "a"), identify=False)
    assert all(not s.identified for s in read_transcript(off / "transcript.words.json").speakers)
    plain = _run(tmp_path / "b", _directory(tmp_path / "b", enrolled=False))
    stages = [s.stage for s in read_manifest(plain / "manifest.json").stages]
    assert "identify" not in stages


def test_mismatched_voiceprint_warns(tmp_path: Path) -> None:
    path = _directory(tmp_path)
    data = yaml.safe_load(path.read_text())
    data["people"][0]["voiceprint"]["revision"] = "f" * 40
    path.write_text(yaml.safe_dump(data))
    folder = _run(tmp_path, path)
    manifest = read_manifest(folder / "manifest.json")
    assert any("enroll again" in w for w in manifest.warnings)
    names = {s.label: s.name for s in read_transcript(folder / "transcript.words.json").speakers}
    assert names["SPEAKER_00"] is None


def test_map_and_merge(tmp_path: Path) -> None:
    folder = _run(tmp_path, None)
    result = runner.invoke(app, ["speakers", "map", str(folder), "--set", "SPEAKER_00=Carla Diaz"])
    assert result.exit_code == 0, result.output
    transcript = read_transcript(folder / "transcript.words.json")
    assert transcript.speakers[0].name == "Carla Diaz"
    assert (folder / "speakers/carla-diaz.flac").exists()
    assert not (folder / "speakers/SPEAKER_00.flac").exists()
    assert "Carla Diaz:" in (folder / "transcript.txt").read_text()
    assert read_manifest(folder / "manifest.json").edits[0]["op"] == "map"

    source, _ = sf.read(FIXTURE)
    result = runner.invoke(
        app, ["speakers", "merge", str(folder), "SPEAKER_01", "--into", "SPEAKER_00"]
    )
    assert result.exit_code == 0, result.output
    transcript = read_transcript(folder / "transcript.words.json")
    assert [s.label for s in transcript.speakers] == ["SPEAKER_00"]
    assert transcript.speakers[0].merged_from == ["SPEAKER_01"]
    assert {w.speaker for w in transcript.words()} == {"SPEAKER_00"}
    assert [p.name for p in (folder / "speakers").glob("*.flac")] == ["carla-diaz.flac"]
    merged, _ = sf.read(folder / "speakers/carla-diaz.flac")
    assert len(merged) == len(source)
    assert abs(merged[(4 * 16000) : (5 * 16000)]).max() > 0.1


def test_enroll_requires_consent_then_stores_voiceprint(tmp_path: Path) -> None:
    folder = _run(tmp_path, None)
    directory = _directory(tmp_path, enrolled=False)
    args = [
        "enroll",
        str(folder),
        "--speaker",
        "SPEAKER_00=alice",
        "--directory",
        str(directory),
        "--embedder",
        "fake",
        "--device",
        "cpu",
    ]
    denied = subprocess.run(["saidby", *args], capture_output=True, text=True, check=False)
    assert denied.returncode == 5
    assert "[consent_missing · exit 5]" in denied.stderr
    assert "ConsentMissingError" not in denied.stderr
    assert "voiceprint" not in directory.read_text()

    allowed = runner.invoke(
        app, [*args, "--consent-source", "signed form", "--consent-declared-by", "Alice"]
    )
    assert allowed.exit_code == 0, allowed.output
    saved = yaml.safe_load(directory.read_text())
    voiceprint = saved["people"][0]["voiceprint"]
    assert voiceprint["model"] == "fake"
    assert voiceprint["consent"]["declared_by"] == "Alice"
    assert list(tmp_path.glob("directory.bak-*.yaml"))
    consent = yaml.safe_load((tmp_path / "consent.yaml").read_text())
    assert consent[0]["person"] == "alice"
    assert (tmp_path / "consent.yaml").read_text().count("signed form") == 1


def test_rerun_with_new_names_removes_stale_tracks(tmp_path: Path) -> None:
    folder = _run(tmp_path, None, keep_intermediates=True)
    assert (folder / "speakers/SPEAKER_00.flac").exists()
    out = tmp_path / "out"
    _run(tmp_path, _directory(tmp_path), keep_intermediates=True)
    assert (out / "tones_2spk_10s/speakers/alice.flac").exists()
    assert not (out / "tones_2spk_10s/speakers/SPEAKER_00.flac").exists()


def test_two_directory_files_merge_and_the_manifest_records_both(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    far = _directory(shared)
    project = tmp_path / "project"
    project.mkdir()
    near = project / "directory.yaml"
    near.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "language": "es",
                "people": [{"id": "bob", "name": "Bobby", "context": "client"}],
                "terms": [{"term": "Acme"}],
            }
        )
    )
    pipeline = Pipeline(
        Settings(device="cpu", language="es", directory=[far, near]),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        embedder=FakeEmbedder(VOICES),
        progress=Progress("none"),
    )
    out = tmp_path / "out"
    assert pipeline.run([FIXTURE], out)[0].status == "ok"
    folder = out / "tones_2spk_10s"
    names = {s.label: s.name for s in read_transcript(folder / "transcript.words.json").speakers}
    assert names == {"SPEAKER_00": "Alice", "SPEAKER_01": "Bobby"}
    record = read_manifest(folder / "manifest.json").directory
    assert record is not None
    assert [f["path"] for f in record["files"]] == [str(far), str(near)]
    assert record["path"] == str(near)
    assert (record["people"], record["terms"]) == (2, 1)


def test_voiceprints_without_consent_are_skipped_and_reported(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    (tmp_path / "consent.yaml").unlink()
    folder = _run(tmp_path, directory)
    manifest = read_manifest(folder / "manifest.json")
    assert any("has no consent record" in w and "alice" in w for w in manifest.warnings)
    assert all(not s.identified for s in read_transcript(folder / "transcript.words.json").speakers)
    assert "identify" not in [s.stage for s in manifest.stages]


def test_the_run_records_why_it_used_the_cpu_and_remembers_the_device(tmp_path: Path) -> None:
    folder = _run(tmp_path, None)
    device = read_manifest(folder / "manifest.json").device
    assert (device.used, device.reason) == ("cpu", "requested_cpu")
    cached = read_cache()
    assert cached is not None
    assert (cached.kind, cached.reason) == ("cpu", "requested_cpu")
