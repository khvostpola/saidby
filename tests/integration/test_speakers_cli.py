# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from saidby.cli import app
from saidby.cli.progress import Progress
from saidby.cli.term import Terminal
from saidby.cli.ui import Ui
from saidby.config.settings import Settings
from saidby.engines.asr.fake import FakeTranscriber
from saidby.engines.diarize.fake import FakeDiarizer
from saidby.errors import UsageError
from saidby.formats.manifest import read_manifest
from saidby.formats.words_json import read_transcript
from saidby.pipeline.runner import Pipeline

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/synthetic/tones_2spk_10s.flac"
RTTM = ROOT / "fixtures/synthetic/tones_2spk_10s.rttm"
runner = CliRunner()
PLAIN = Terminal(tty=True, color=False, truecolor=False, columns=80)

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _folder(tmp_path: Path) -> Path:
    pipeline = Pipeline(
        Settings(device="cpu", language="es"),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("none"),
    )
    assert pipeline.run([FIXTURE], tmp_path / "out")[0].status == "ok"
    return tmp_path / "out" / "tones_2spk_10s"


def _directory(tmp_path: Path) -> Path:
    path = tmp_path / "directory.yaml"
    path.write_text(
        "# team\nversion: 1\nlanguage: es\npeople:\n  - id: ana\n    name: Ana Gómez\n"
        "    aliases: [Anita]\n",
        encoding="utf-8",
    )
    return path


def _map(folder: Path, directory: Path, *args: str) -> object:
    return runner.invoke(
        app, ["speakers", "map", str(folder), "--directory", str(directory), *args]
    )


def _names(folder: Path) -> dict[str, tuple[str | None, str | None]]:
    transcript = read_transcript(folder / "transcript.words.json")
    return {s.label: (s.id, s.name) for s in transcript.speakers}


def test_a_name_in_the_directory_resolves_to_its_person(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    result = _map(folder, directory, "--set", "SPEAKER_00=ana gómez")
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert _names(folder)["SPEAKER_00"] == ("ana", "Ana Gómez")
    assert (folder / "speakers/ana.flac").exists()


def test_an_alias_and_an_id_resolve_too(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    assert _map(folder, directory, "--set", "SPEAKER_00=Anita").exit_code == 0  # type: ignore[attr-defined]
    assert _names(folder)["SPEAKER_00"] == ("ana", "Ana Gómez")
    folder2 = _folder(tmp_path / "second")
    assert _map(folder2, directory, "--set", "SPEAKER_01=ANA").exit_code == 0  # type: ignore[attr-defined]
    assert _names(folder2)["SPEAKER_01"] == ("ana", "Ana Gómez")


def test_a_new_name_is_not_added_without_a_terminal_unless_asked(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    before = directory.read_text(encoding="utf-8")
    result = _map(folder, directory, "--set", "SPEAKER_01=Carla Díaz")
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert _names(folder)["SPEAKER_01"] == ("carla-diaz", "Carla Díaz")
    assert directory.read_text(encoding="utf-8") == before


def test_add_missing_writes_the_person_to_the_directory(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    result = _map(folder, directory, "--set", "SPEAKER_01=Carla Díaz", "--add-missing")
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert "added carla-diaz (Carla Díaz)" in result.output  # type: ignore[attr-defined]
    saved = yaml.safe_load(directory.read_text(encoding="utf-8"))
    assert [p["id"] for p in saved["people"]] == ["ana", "carla-diaz"]
    assert "# team" in directory.read_text(encoding="utf-8")
    assert list(tmp_path.glob("directory.bak-*.yaml"))
    assert _names(folder)["SPEAKER_01"] == ("carla-diaz", "Carla Díaz")


def test_on_a_terminal_it_asks_before_adding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    answers = iter(["", "n"])
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    speakers_module = sys.modules["saidby.cli.speakers"]
    monkeypatch.setattr("saidby.cli.ui.interactive_streams", lambda: True)
    monkeypatch.setattr(
        speakers_module, "_ui", lambda: Ui(PLAIN, input_fn=fake_input, out=io.StringIO())
    )
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    result = _map(folder, directory, "--set", "SPEAKER_00=Carla Díaz", "--set", "SPEAKER_01=Ben")
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert "Add it to" in prompts[0]
    ids = [p["id"] for p in yaml.safe_load(directory.read_text(encoding="utf-8"))["people"]]
    assert ids == ["ana", "carla-diaz"]
    assert _names(folder)["SPEAKER_01"] == ("ben", "Ben")


def test_a_free_name_without_any_directory_still_works(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    result = runner.invoke(app, ["speakers", "map", str(folder), "--set", "SPEAKER_00=Carla Díaz"])
    assert result.exit_code == 0, result.output
    assert _names(folder)["SPEAKER_00"] == ("carla-diaz", "Carla Díaz")


def test_a_name_with_no_letters_cannot_be_added_automatically(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    result = _map(folder, directory, "--set", "SPEAKER_00=李雷", "--add-missing")
    assert isinstance(result.exception, UsageError)  # type: ignore[attr-defined]
    assert "--id" in str(result.exception)  # type: ignore[attr-defined]


def test_show_prints_a_table_and_json_on_request(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    assert _map(folder, directory, "--set", "SPEAKER_00=ana").exit_code == 0  # type: ignore[attr-defined]
    table = runner.invoke(app, ["speakers", "show", str(folder)]).output.splitlines()
    assert table[0].split() == ["speaker", "name", "speech", "named", "by", "track"]
    assert table[1].split()[:2] == ["SPEAKER_00", "Ana"]
    assert "you" in table[1]
    assert "speakers/ana.flac" in table[1]
    assert table[2].split()[:2] == ["SPEAKER_01", "-"]
    rows = json.loads(runner.invoke(app, ["speakers", "show", str(folder), "--json"]).output)
    assert [r["label"] for r in rows] == ["SPEAKER_00", "SPEAKER_01"]
    assert read_manifest(folder / "manifest.json").edits[-1]["op"] == "map"
