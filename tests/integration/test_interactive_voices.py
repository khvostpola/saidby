# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
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
from saidby.errors import InputError, UsageError
from saidby.interactive.voices import store_voices
from saidby.pipeline.runner import Pipeline
from saidby.speakers import remap

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/synthetic/tones_2spk_10s.flac"
RTTM = ROOT / "fixtures/synthetic/tones_2spk_10s.rttm"
PLAIN = Terminal(tty=True, color=False, truecolor=False, columns=100)
runner = CliRunner()

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _folder(tmp_path: Path, *, named: bool = True) -> Path:
    pipeline = Pipeline(
        Settings(device="cpu", language="es"),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("none"),
    )
    assert pipeline.run([FIXTURE], tmp_path / "out")[0].status == "ok"
    folder = tmp_path / "out" / "tones_2spk_10s"
    if named:
        remap.map_speaker(folder, "SPEAKER_00", "alice", "Alice")
        remap.map_speaker(folder, "SPEAKER_01", "bob", "Bob")
    return folder


def _directory(tmp_path: Path) -> Path:
    path = tmp_path / "directory.yaml"
    path.write_text(
        "version: 1\nlanguage: es\npeople:\n  - id: alice\n    name: Alice\n"
        "  - id: bob\n    name: Bob\n"
    )
    return path


def _session(answers: list[str]) -> tuple[Ui, io.StringIO, list[str]]:
    feed = iter(answers)
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(feed)

    out = io.StringIO()
    return Ui(PLAIN, input_fn=fake_input, out=out), out, prompts


def _store(ui: Ui, folder: Path, directory: Path) -> object:
    return store_voices(
        ui,
        folder,
        directory,
        directory.with_name("consent.yaml"),
        embedder_name="fake",
        device="cpu",
        channel="phone",
    )


def _people(directory: Path) -> dict[str, dict[str, object]]:
    return {p["id"]: p for p in yaml.safe_load(directory.read_text())["people"]}


def _consent(directory: Path) -> list[dict[str, str]]:
    path = directory.with_name("consent.yaml")
    return yaml.safe_load(path.read_text()) if path.exists() else []


def test_each_person_who_agreed_gets_a_voiceprint_and_a_consent_record(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    ui, out, prompts = _session(["y", "signed form", "", "y", "the team lead", ""])
    result = _store(ui, folder, directory)
    assert result is not None
    people = _people(directory)
    assert "voiceprint" in people["alice"]
    assert "voiceprint" in people["bob"]
    assert [(c["person"], c["source"], c["declared_by"]) for c in _consent(directory)] == [
        ("alice", "signed form", "Alice"),
        ("bob", "signed form", "the team lead"),
    ]
    asked_source = [p for p in prompts if "How was consent given?" in p]
    assert len(asked_source) == 1
    text = out.getvalue()
    assert any("Did Alice agree to have their voiceprint stored?" in p for p in prompts)
    assert "2 voiceprints stored" in text
    assert "alice:" in text
    assert "bob:" in text
    assert list(tmp_path.glob("directory.bak-*.yaml"))


def test_a_person_who_did_not_agree_is_not_stored_and_leaves_no_record(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    ui, out, _ = _session(["n", "y", "signed form", "", ""])
    _store(ui, folder, directory)
    people = _people(directory)
    assert "voiceprint" not in people["alice"]
    assert "voiceprint" in people["bob"]
    assert [c["person"] for c in _consent(directory)] == ["bob"]
    assert "no consent, so no voiceprint" in out.getvalue()
    assert "1 voiceprint stored" in out.getvalue()


def test_nobody_agreeing_changes_nothing(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    before = directory.read_text()
    ui, out, _ = _session(["n", "n"])
    assert _store(ui, folder, directory) is None
    assert directory.read_text() == before
    assert _consent(directory) == []
    assert not list(tmp_path.glob("directory.bak-*.yaml"))
    assert "no voiceprint was stored" in out.getvalue()


def test_declining_the_final_question_changes_nothing(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    before = directory.read_text()
    ui, out, _ = _session(["y", "signed form", "", "n", "n"])
    assert _store(ui, folder, directory) is None
    assert directory.read_text() == before
    assert _consent(directory) == []
    assert "nothing was stored" in out.getvalue()


def test_an_interruption_before_the_end_changes_nothing(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    before = directory.read_text()
    feed = iter(["y", "signed form", ""])

    def fake_input(prompt: str) -> str:
        try:
            return next(feed)
        except StopIteration:
            raise KeyboardInterrupt from None

    ui = Ui(PLAIN, input_fn=fake_input, out=io.StringIO())
    with pytest.raises(KeyboardInterrupt):
        _store(ui, folder, directory)
    assert directory.read_text() == before
    assert _consent(directory) == []


def test_consent_already_on_record_is_shown_and_not_asked_again(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    directory.with_name("consent.yaml").write_text(
        yaml.safe_dump(
            [
                {
                    "person": "alice",
                    "source": "email",
                    "declared_by": "Alice",
                    "date": "2026-10-01",
                }
            ]
        )
    )
    ui, out, prompts = _session(["", "n", ""])
    assert _store(ui, folder, directory) is not None
    text = out.getvalue()
    assert "consent on record: email, declared by Alice, 2026-10-01" in text
    assert not any("Did Alice agree" in p for p in prompts)
    assert "voiceprint" in _people(directory)["alice"]
    assert [c["person"] for c in _consent(directory)] == ["alice"]


def test_replacing_an_existing_voiceprint_is_off_unless_asked(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    ui, _, _ = _session(["y", "signed form", "", "n", ""])
    _store(ui, folder, directory)
    before = _people(directory)["alice"]["voiceprint"]
    ui, out, prompts = _session(["", "n"])
    assert _store(ui, folder, directory) is None
    assert any("Replace the voiceprint?" in p for p in prompts)
    assert "already has a voiceprint" in out.getvalue()
    assert _people(directory)["alice"]["voiceprint"] == before


def test_a_missing_original_recording_stops_before_any_consent_is_recorded(
    tmp_path: Path,
) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    manifest = folder / "manifest.json"
    data = json.loads(manifest.read_text())
    data["source"]["path"] = "gone.m4a"
    manifest.write_text(json.dumps(data))
    ui, _, _ = _session(["y", "signed form", "", "n", ""])
    with pytest.raises(InputError, match=r"original recording not found: gone\.m4a"):
        _store(ui, folder, directory)
    assert _consent(directory) == []
    assert "voiceprint" not in _people(directory)["alice"]


def test_voices_without_a_name_are_pointed_to_speakers_map(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path, named=False), _directory(tmp_path)
    ui, out, _ = _session([])
    assert _store(ui, folder, directory) is None
    text = out.getvalue()
    assert "SPEAKER_00, SPEAKER_01 have no name yet" in text
    assert "saidby speakers map -i" in text
    assert "no named voice to store" in text


def test_a_named_voice_missing_from_the_file_says_where_to_look(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    directory = tmp_path / "other.yaml"
    directory.write_text("version: 1\nlanguage: es\npeople:\n  - id: alice\n    name: Alice\n")
    ui, out, _ = _session(["n"])
    assert _store(ui, folder, directory) is None
    assert "Bob are not in" in out.getvalue()
    assert "pass --directory" in out.getvalue()


def test_the_command_needs_a_terminal_and_refuses_flags_that_clash(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    base = ["enroll", str(folder), "--directory", str(directory)]
    plain = runner.invoke(app, [*base, "-i"])
    assert isinstance(plain.exception, UsageError)
    assert "needs a terminal; without one, use: saidby enroll" in str(plain.exception)
    both = runner.invoke(app, [*base, "-i", "--speaker", "SPEAKER_00=alice"])
    assert "either --speaker or -i" in str(both.exception)
    clash = runner.invoke(app, [*base, "-i", "--consent-source", "form"])
    assert "asks about consent itself" in str(clash.exception)
    neither = runner.invoke(app, base)
    assert "pass --speaker LABEL=PERSON, or -i" in str(neither.exception)


def test_the_command_runs_the_whole_flow_on_a_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    ui, _, _ = _session(["y", "signed form", "", "n", ""])
    module = sys.modules["saidby.cli.enroll"]
    monkeypatch.setattr(module, "ensure_terminal", lambda command: None)
    monkeypatch.setattr(module, "Ui", lambda: ui)
    result = runner.invoke(
        app,
        [
            "enroll",
            str(folder),
            "-i",
            "--directory",
            str(directory),
            "--embedder",
            "fake",
            "--device",
            "cpu",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "voiceprint" in _people(directory)["alice"]
    assert "voiceprint" not in _people(directory)["bob"]


def test_the_consent_source_has_no_default_and_cannot_be_empty(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    ui, out, prompts = _session(
        [
            "y",
            "",
            "a signed form",
            "",
            "n",
            "",
        ]
    )
    _store(ui, folder, directory)
    assert "this cannot be empty" in out.getvalue()
    source_prompts = [p for p in prompts if "How was consent given?" in p]
    assert len(source_prompts) == 2
    assert "[for example: signed form]" in source_prompts[0]
    assert _consent(directory)[0]["source"] == "a signed form"


def test_a_failed_enrollment_leaves_no_consent_behind(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    result = runner.invoke(
        app,
        [
            "enroll",
            str(folder),
            "--speaker",
            "SPEAKER_09=alice",
            "--directory",
            str(directory),
            "--embedder",
            "fake",
            "--device",
            "cpu",
            "--consent-source",
            "signed form",
            "--consent-declared-by",
            "Alice",
        ],
    )
    assert isinstance(result.exception, UsageError)
    assert "no usable speech for speaker" in str(result.exception)
    assert _consent(directory) == []
    assert "voiceprint" not in _people(directory)["alice"]


def test_enrolling_leaves_no_decoded_copy_of_the_recording_behind(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    assert not (folder / ".work").exists()
    ui, _, _ = _session(["y", "signed form", "", "n", ""])
    _store(ui, folder, directory)
    assert "voiceprint" in _people(directory)["alice"]
    assert not (folder / ".work").exists()


def test_a_consent_file_elsewhere_is_flagged(tmp_path: Path) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    elsewhere = tmp_path / "other" / "consent.yaml"
    elsewhere.parent.mkdir()
    result = runner.invoke(
        app,
        [
            "enroll",
            str(folder),
            "--speaker",
            "SPEAKER_00=alice",
            "--directory",
            str(directory),
            "--consent-file",
            str(elsewhere),
            "--embedder",
            "fake",
            "--device",
            "cpu",
            "--consent-source",
            "signed form",
            "--consent-declared-by",
            "Alice",
        ],
    )
    assert result.exit_code == 0, result.output
    assert f"saidby process only reads {directory.with_name('consent.yaml')}" in result.output
    assert elsewhere.exists()


def test_without_speaker_the_command_is_guided_on_a_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder, directory = _folder(tmp_path), _directory(tmp_path)
    ui, _, prompts = _session(["y", "signed form", "", "n", ""])
    monkeypatch.setattr("saidby.cli.ui.interactive_streams", lambda: True)
    monkeypatch.setattr(sys.modules["saidby.cli.enroll"], "Ui", lambda: ui)
    base = ["enroll", str(folder), "--directory", str(directory), "--embedder", "fake"]
    result = runner.invoke(app, [*base, "--device", "cpu"])
    assert result.exit_code == 0, result.output
    assert len(prompts) == 5
    assert "voiceprint" in _people(directory)["alice"]
    flags = runner.invoke(app, [*base, "--consent-source", "form"])
    assert "pass --speaker LABEL=PERSON, or -i" in str(flags.exception)
    monkeypatch.setenv("SAIDBY_INTERACTIVE", "false")
    off = runner.invoke(app, base)
    assert "pass --speaker LABEL=PERSON, or -i" in str(off.exception)
