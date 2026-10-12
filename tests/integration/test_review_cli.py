# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from saidby.cli import app
from saidby.cli.progress import Progress
from saidby.config.settings import Settings
from saidby.engines.asr.fake import FakeTranscriber
from saidby.engines.diarize.fake import FakeDiarizer
from saidby.errors import UsageError
from saidby.formats.corrections_log import read_corrections
from saidby.formats.manifest import read_manifest
from saidby.formats.words_json import read_transcript
from saidby.pipeline.runner import Pipeline

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/synthetic/tones_2spk_10s.flac"
RTTM = ROOT / "fixtures/synthetic/tones_2spk_10s.rttm"
runner = CliRunner()

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _folder(tmp_path: Path) -> Path:
    pipeline = Pipeline(
        Settings(device="cpu", language="es", compare="fake"),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        compare_diarizer=FakeDiarizer(turn_s=2.0, speakers=3),
        progress=Progress("none"),
    )
    assert pipeline.run([FIXTURE], tmp_path)[0].status == "ok"
    return tmp_path / "tones_2spk_10s"


def _directory(tmp_path: Path) -> Path:
    path = tmp_path / "directory.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "language": "es",
                "people": [],
                "terms": [{"term": "Acme", "variants": ["akme"]}],
            }
        )
    )
    return path


def test_review_edits_text_speaker_and_state(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    before = read_transcript(folder / "transcript.words.json")
    result = runner.invoke(
        app,
        ["review", str(folder), "--kinds", "diarization", "--limit", "3"],
        input="Acme nuevo texto\n@SPEAKER_01\n/s\n",
    )
    assert result.exit_code == 0, result.output
    assert "saved 1 text corrections" in result.output
    after = read_transcript(folder / "transcript.words.json")
    sources = [w.source for w in after.words()]
    assert "review" in sources
    assert len(after.words()) != len(before.words()) or sources != ["asr"] * len(sources)
    log = read_corrections(folder / "corrections.jsonl")
    assert [(c.by, c.status) for c in log] == [("review", "accepted")]
    assert "Acme" in (folder / "transcript.txt").read_text()
    manifest = read_manifest(folder / "manifest.json")
    assert manifest.edits[-1]["op"] == "review"
    assert manifest.files["corrections"] == "corrections.jsonl"
    state = [json.loads(x) for x in (folder / "logs/review.jsonl").read_text().splitlines()]
    assert [s["decision"] for s in state] == ["edited", "speaker"]
    assert "Acme" not in (folder / "logs/review.jsonl").read_text()

    again = runner.invoke(app, ["review", str(folder), "--kinds", "diarization"], input="/q\n")
    assert again.exit_code == 0
    assert "edited" not in again.output


def test_review_keeps_answered_edits_when_a_later_answer_fails(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    result = runner.invoke(
        app,
        ["review", str(folder), "--kinds", "diarization", "--limit", "3"],
        input="Acme nuevo texto\n@NOBODY\n",
    )
    assert isinstance(result.exception, UsageError)
    log = read_corrections(folder / "corrections.jsonl")
    assert [(c.by, c.status) for c in log] == [("review", "accepted")]
    assert "review" in [w.source for w in read_transcript(folder / "transcript.words.json").words()]
    assert read_manifest(folder / "manifest.json").edits[-1]["op"] == "review"
    state = [json.loads(x) for x in (folder / "logs/review.jsonl").read_text().splitlines()]
    assert [s["decision"] for s in state] == ["edited"]


def test_review_nothing_to_review(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    result = runner.invoke(app, ["review", str(folder), "--kinds", "llm_rejected"])
    assert result.exit_code == 0
    assert "nothing to review" in result.output


def test_review_offers_directory_variants(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    directory = _directory(tmp_path)
    result = runner.invoke(
        app,
        [
            "review",
            str(folder),
            "--kinds",
            "diarization",
            "--limit",
            "1",
            "--directory",
            str(directory),
            "--yes",
        ],
        input="Acme\n",
    )
    assert result.exit_code == 0, result.output
    original = read_corrections(folder / "corrections.jsonl")[0].from_
    assert original
    variants = yaml.safe_load(directory.read_text())["terms"][0]["variants"]
    assert variants == ["akme", original]
    backups = list(tmp_path.glob("directory.bak-*.yaml"))
    assert len(backups) == 1
    assert yaml.safe_load(backups[0].read_text())["terms"][0]["variants"] == ["akme"]
    assert "added 1 variants" in result.output


def test_review_directory_prompt_can_be_declined(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    directory = _directory(tmp_path)
    before = directory.read_text()
    result = runner.invoke(
        app,
        [
            "review",
            str(folder),
            "--kinds",
            "diarization",
            "--limit",
            "1",
            "--directory",
            str(directory),
        ],
        input="Acme\nn\n",
    )
    assert result.exit_code == 0, result.output
    assert directory.read_text() == before
