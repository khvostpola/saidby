# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import shutil
import sys
from pathlib import Path
from typing import Any, ClassVar

import pytest
from typer.testing import CliRunner

from saidby.cli import app
from saidby.cli.next_steps import read_state
from saidby.cli.progress import Progress
from saidby.config.settings import Settings
from saidby.engines.asr.fake import FakeTranscriber
from saidby.engines.diarize.fake import FakeDiarizer
from saidby.pipeline.job import RecordingResult
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


def test_a_fresh_folder_has_unnamed_speakers_and_doubtful_spans(tmp_path: Path) -> None:
    state = read_state(_folder(tmp_path))
    assert state is not None
    assert state.unnamed == ("SPEAKER_00", "SPEAKER_01")
    assert state.doubtful > 0


def test_naming_the_speakers_clears_the_first_hint(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    args = ["speakers", "map", str(folder), "--set", "SPEAKER_00=Ana", "--set", "SPEAKER_01=Ben"]
    assert runner.invoke(app, args).exit_code == 0
    state = read_state(folder)
    assert state is not None
    assert state.unnamed == ()


def test_something_that_is_not_a_result_folder_has_no_state(tmp_path: Path) -> None:
    assert read_state(tmp_path) is None


class _StubPipeline:
    results: ClassVar[list[RecordingResult]] = []

    def __init__(self, settings: Settings, **_: Any) -> None:
        pass

    def run(self, inputs: list[Path], out: Path) -> list[RecordingResult]:
        return self.results


def _process(monkeypatch: pytest.MonkeyPatch, results: list[RecordingResult], *flags: str) -> str:
    _StubPipeline.results = results
    monkeypatch.setattr(sys.modules["saidby.cli.process"], "Pipeline", _StubPipeline)
    result = runner.invoke(app, ["process", "call.m4a", *flags])
    assert result.exit_code == 0, result.output
    return result.output


def test_process_ends_with_the_next_steps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = _folder(tmp_path)
    output = _process(monkeypatch, [RecordingResult("tones", folder, "ok", 0)])
    lines = output.rstrip().splitlines()
    assert lines[-2].startswith("  name:")
    assert f"saidby speakers map -i {folder}" in lines[-2]
    assert lines[-1].startswith("  review:")
    assert "doubtful span" in lines[-1]


@pytest.mark.parametrize("mode", ["json", "none"])
def test_machine_modes_get_no_footer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    folder = _folder(tmp_path)
    output = _process(monkeypatch, [RecordingResult("tones", folder, "ok", 0)], "--progress", mode)
    assert "saidby speakers map" not in output


def test_a_failed_file_gets_no_footer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = _folder(tmp_path)
    _StubPipeline.results = [RecordingResult("tones", folder, "failed", 6, "StageError")]
    monkeypatch.setattr(sys.modules["saidby.cli.process"], "Pipeline", _StubPipeline)
    result = runner.invoke(app, ["process", "call.m4a"])
    assert "saidby speakers map" not in result.output
