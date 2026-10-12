# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
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
from saidby.formats.directory_set import load_directory_set
from saidby.formats.manifest import read_manifest
from saidby.formats.words_json import read_transcript
from saidby.interactive.flows import name_voices
from saidby.interactive.listen import Step, listen
from saidby.pipeline.runner import Pipeline
from saidby.speakers.remap import Folder

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/synthetic/tones_2spk_10s.flac"
RTTM = ROOT / "fixtures/synthetic/tones_2spk_10s.rttm"
PLAIN = Terminal(tty=True, color=False, truecolor=False, columns=100)
runner = CliRunner()

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
        "  - id: ben\n    name: Ben Ruiz\n"
    )
    return path


class Played:
    def __init__(self, found: bool = True) -> None:
        self.calls: list[tuple[Path, float, float]] = []
        self.found = found

    def __call__(self, path: Path, start: float, duration: float) -> bool:
        self.calls.append((path, start, duration))
        return self.found


def _session(answers: list[str]) -> tuple[Ui, io.StringIO, list[str]]:
    feed = iter(answers)
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(feed)

    out = io.StringIO()
    return Ui(PLAIN, input_fn=fake_input, out=out), out, prompts


def _names(folder: Path) -> dict[str, tuple[str | None, str | None]]:
    transcript = read_transcript(folder / "transcript.words.json")
    return {s.label: (s.id, s.name) for s in transcript.speakers}


def test_listening_shows_each_voice_with_its_time_turns_and_a_clean_sample(tmp_path: Path) -> None:
    folder = Folder(_folder(tmp_path))
    ui, out, _ = _session([""])
    assert listen(ui, folder, title="Speakers in out", player=Played()) is Step.CONTINUE
    text = out.getvalue()
    assert "Speakers in out" in text
    for expected in ("voice", "clean sample", "SPEAKER_00", "SPEAKER_01"):
        assert expected in text
    assert "speakers/SPEAKER_00.flac" in text
    assert "Enter I listened, continue   p play a sample   s skip naming   q quit" in text
    assert "file://" in text


def test_p_plays_the_clean_sample_of_every_voice_then_asks_again(tmp_path: Path) -> None:
    folder = Folder(_folder(tmp_path))
    player = Played()
    ui, out, prompts = _session(["p", "P", ""])
    assert listen(ui, folder, title="t", player=player) is Step.CONTINUE
    assert len(player.calls) == 4
    first = player.calls[0]
    assert first[0] == folder.out_dir / "speakers/SPEAKER_00.flac"
    assert first[2] > 0
    assert "▶ SPEAKER_00" in out.getvalue()
    assert len(prompts) == 3


def test_without_ffplay_it_prints_the_path_instead(tmp_path: Path) -> None:
    folder = Folder(_folder(tmp_path))
    ui, out, _ = _session(["p", ""])
    listen(ui, folder, title="t", player=Played(found=False))
    assert "ffplay not found, open this file instead:" in out.getvalue()
    assert "speakers/SPEAKER_00.flac" in out.getvalue()


@pytest.mark.parametrize(("key", "step"), [("s", Step.SKIP), ("q", Step.QUIT), ("", Step.CONTINUE)])
def test_the_keys_choose_what_happens_next(tmp_path: Path, key: str, step: Step) -> None:
    ui, _, _ = _session([key])
    assert listen(ui, Folder(_folder(tmp_path)), title="t", player=Played()) is step


def test_an_unknown_key_is_refused_and_asked_again(tmp_path: Path) -> None:
    ui, out, prompts = _session(["x", ""])
    listen(ui, Folder(_folder(tmp_path)), title="t", player=Played())
    assert "type Enter, p, s or q" in out.getvalue()
    assert len(prompts) == 2


def test_naming_a_directory_person_and_a_new_one(tmp_path: Path) -> None:
    out_dir, directory = _folder(tmp_path), _directory(tmp_path)
    ui, out, prompts = _session(["", "ana gómez", "Carla Díaz", ""])
    naming = name_voices(ui, out_dir, [directory], title="t", player=Played())
    assert naming is not None
    assert naming.applied == [
        ("SPEAKER_00", "ana", "Ana Gómez"),
        ("SPEAKER_01", "carla-diaz", "Carla Díaz"),
    ]
    assert naming.added == ["Carla Díaz"]
    assert _names(out_dir) == {
        "SPEAKER_00": ("ana", "Ana Gómez"),
        "SPEAKER_01": ("carla-diaz", "Carla Díaz"),
    }
    assert (out_dir / "speakers/ana.flac").exists()
    assert (out_dir / "speakers/carla-diaz.flac").exists()
    ids = [p.id for p in load_directory_set([directory]).merged.people]
    assert ids == ["ana", "ben", "carla-diaz"]
    assert "# team" in directory.read_text()
    assert list(tmp_path.glob("directory.bak-*.yaml"))
    assert "Carla Díaz added to" in out.getvalue()
    assert "2 tracks renamed" in out.getvalue()
    assert "[keep SPEAKER_00]" in prompts[1]
    ops = [e["op"] for e in read_manifest(out_dir / "manifest.json").edits]
    assert ops == ["map", "map"]


def test_a_person_cannot_be_two_voices_at_once(tmp_path: Path) -> None:
    out_dir, directory = _folder(tmp_path), _directory(tmp_path)
    ui, out, _ = _session(["", "ana", "ANA", "ben", ""])
    naming = name_voices(ui, out_dir, [directory], title="t", player=Played())
    assert naming is not None
    assert (
        'ANA is already SPEAKER_00. Pick another name, or use "saidby speakers merge"'
        in out.getvalue()
    )
    assert _names(out_dir)["SPEAKER_01"] == ("ben", "Ben Ruiz")


def test_the_same_new_name_cannot_be_used_twice(tmp_path: Path) -> None:
    out_dir = _folder(tmp_path)
    ui, out, _ = _session(["", "Carla", "Carla", "Carlos", ""])
    naming = name_voices(ui, out_dir, [], title="t", player=Played())
    assert naming is not None
    assert "Carla is already SPEAKER_00" in out.getvalue()
    assert [a[1] for a in naming.applied] == ["carla", "carlos"]


def test_keeping_everything_changes_nothing(tmp_path: Path) -> None:
    out_dir, directory = _folder(tmp_path), _directory(tmp_path)
    before = (out_dir / "manifest.json").read_text()
    ui, out, _ = _session(["", "", "", ""])
    assert name_voices(ui, out_dir, [directory], title="t", player=Played()) is None
    assert "Nothing to rename." in out.getvalue()
    assert (out_dir / "manifest.json").read_text() == before


def test_declining_the_confirmation_changes_nothing(tmp_path: Path) -> None:
    out_dir, directory = _folder(tmp_path), _directory(tmp_path)
    before = directory.read_text()
    ui, out, _ = _session(["", "ana", "Carla", "n"])
    assert name_voices(ui, out_dir, [directory], title="t", player=Played()) is None
    assert "nothing was changed" in out.getvalue()
    assert _names(out_dir)["SPEAKER_00"] == (None, None)
    assert directory.read_text() == before


def test_skipping_and_quitting_leave_the_folder_alone(tmp_path: Path) -> None:
    out_dir = _folder(tmp_path)
    for key, message in (("s", "naming skipped"), ("q", "stopped")):
        ui, out, _ = _session([key])
        assert name_voices(ui, out_dir, [], title="t", player=Played()) is None
        assert message in out.getvalue()
    assert _names(out_dir)["SPEAKER_00"] == (None, None)


def test_without_a_directory_a_free_name_becomes_an_id(tmp_path: Path) -> None:
    out_dir = _folder(tmp_path)
    ui, out, _ = _session(["", "Carla Díaz", "", ""])
    naming = name_voices(ui, out_dir, [], title="t", player=Played())
    assert naming is not None
    assert naming.added == []
    assert _names(out_dir)["SPEAKER_00"] == ("carla-diaz", "Carla Díaz")
    assert "will be added" not in out.getvalue()
    assert "(new name)" in out.getvalue()


def test_the_command_needs_a_terminal_and_refuses_set_with_i(tmp_path: Path) -> None:
    out_dir = _folder(tmp_path)
    result = runner.invoke(app, ["speakers", "map", str(out_dir), "-i"])
    assert isinstance(result.exception, UsageError)
    assert "needs a terminal; without one, use: saidby speakers map" in str(result.exception)
    both = runner.invoke(app, ["speakers", "map", str(out_dir), "-i", "--set", "SPEAKER_00=ana"])
    assert "either --set or -i" in str(both.exception)
    neither = runner.invoke(app, ["speakers", "map", str(out_dir)])
    assert "pass --set LABEL=PERSON, or -i" in str(neither.exception)


def test_the_command_runs_the_whole_flow_on_a_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir, directory = _folder(tmp_path), _directory(tmp_path)
    ui, _, _ = _session(["", "ben", "", ""])
    module = sys.modules["saidby.cli.speakers"]
    monkeypatch.setattr(module, "ensure_terminal", lambda command: None)
    monkeypatch.setattr(module, "_ui", lambda: ui)
    result = runner.invoke(
        app, ["speakers", "map", str(out_dir), "-i", "--directory", str(directory)]
    )
    assert result.exit_code == 0, result.output
    assert _names(out_dir)["SPEAKER_00"] == ("ben", "Ben Ruiz")
    assert yaml.safe_load(directory.read_text())["people"][1]["id"] == "ben"


def test_a_voice_that_keeps_its_name_still_blocks_that_name_for_another(tmp_path: Path) -> None:
    from saidby.speakers import remap

    out_dir, directory = _folder(tmp_path), _directory(tmp_path)
    remap.map_speaker(out_dir, "SPEAKER_00", "ana", "Ana Gómez")
    ui, out, _ = _session(["", "", "ana", "ben", ""])
    naming = name_voices(ui, out_dir, [directory], title="t", player=Played())
    assert naming is not None
    assert "ana is already SPEAKER_00" in out.getvalue()
    assert _names(out_dir) == {
        "SPEAKER_00": ("ana", "Ana Gómez"),
        "SPEAKER_01": ("ben", "Ben Ruiz"),
    }


def test_a_new_name_that_makes_an_existing_id_is_refused_whatever_its_accents(
    tmp_path: Path,
) -> None:
    from saidby.speakers import remap

    out_dir = _folder(tmp_path)
    remap.map_speaker(out_dir, "SPEAKER_00", "maria", "Maria")
    ui, out, _ = _session(["", "", "María", "Mariana", ""])
    naming = name_voices(ui, out_dir, [], title="t", player=Played())
    assert naming is not None
    assert "María is already SPEAKER_00" in out.getvalue()
    assert _names(out_dir)["SPEAKER_01"] == ("mariana", "Mariana")


def test_new_names_that_make_the_same_id_cannot_both_be_chosen(tmp_path: Path) -> None:
    out_dir = _folder(tmp_path)
    ui, out, _ = _session(["", "Maria", "maría", "Marcos", ""])
    naming = name_voices(ui, out_dir, [], title="t", player=Played())
    assert naming is not None
    assert "maría is already SPEAKER_00" in out.getvalue()
    assert [a[1] for a in naming.applied] == ["maria", "marcos"]


def test_a_name_with_no_letters_or_digits_is_refused(tmp_path: Path) -> None:
    out_dir = _folder(tmp_path)
    ui, out, _ = _session(["", "???", "Carla", "", ""])
    naming = name_voices(ui, out_dir, [], title="t", player=Played())
    assert naming is not None
    assert "use letters or digits in the name" in out.getvalue()


def test_the_promised_id_is_the_one_that_gets_written(tmp_path: Path) -> None:
    out_dir = _folder(tmp_path)
    directory = tmp_path / "d.yaml"
    directory.write_text("version: 1\nlanguage: es\npeople:\n  - id: ana-gomez\n    name: Ana\n")
    ui, out, _ = _session(["", "Ana Gómez", "", ""])
    naming = name_voices(ui, out_dir, [directory], title="t", player=Played())
    assert naming is not None
    assert "speakers/ana-gomez-2.flac" in out.getvalue()
    assert naming.applied[0][1] == "ana-gomez-2"
    ids = [p.id for p in load_directory_set([directory]).merged.people]
    assert ids == ["ana-gomez", "ana-gomez-2"]
    assert (out_dir / "speakers/ana-gomez-2.flac").exists()


def test_without_set_the_command_is_guided_on_a_terminal_unless_turned_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir, directory = _folder(tmp_path), _directory(tmp_path)
    ui, _, prompts = _session(["", "ben", "", ""])
    monkeypatch.setattr("saidby.cli.ui.interactive_streams", lambda: True)
    monkeypatch.setattr(sys.modules["saidby.cli.speakers"], "_ui", lambda: ui)
    result = runner.invoke(app, ["speakers", "map", str(out_dir), "--directory", str(directory)])
    assert result.exit_code == 0, result.output
    assert len(prompts) == 4
    assert _names(out_dir)["SPEAKER_00"] == ("ben", "Ben Ruiz")
    monkeypatch.setenv("SAIDBY_INTERACTIVE", "false")
    result = runner.invoke(app, ["speakers", "map", str(out_dir)])
    assert "pass --set LABEL=PERSON, or -i" in str(result.exception)


def test_with_the_questions_off_a_new_name_is_not_offered_for_the_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir, directory = _folder(tmp_path), _directory(tmp_path)
    before = directory.read_text()
    monkeypatch.setattr("saidby.cli.ui.interactive_streams", lambda: True)
    monkeypatch.setenv("SAIDBY_INTERACTIVE", "false")
    result = runner.invoke(
        app,
        [
            "speakers",
            "map",
            str(out_dir),
            "--directory",
            str(directory),
            "--set",
            "SPEAKER_00=Carla",
        ],
    )
    assert result.exit_code == 0, result.output
    assert directory.read_text() == before
    assert _names(out_dir)["SPEAKER_00"] == ("carla", "Carla")
