# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
import sys
from pathlib import Path
from typing import Any, ClassVar

import pytest
from typer.testing import CliRunner

from saidby.cli import app
from saidby.cli.term import Terminal
from saidby.cli.ui import Ui
from saidby.config.settings import Settings
from saidby.errors import UsageError
from saidby.interactive.plan import plan_run, split_terms

PLAIN = Terminal(tty=True, color=False, truecolor=False, columns=100)
runner = CliRunner()
INPUTS = [Path("call.m4a")]


def _session(answers: list[str]) -> tuple[Ui, io.StringIO, list[str]]:
    feed = iter(answers)
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(feed)

    out = io.StringIO()
    return Ui(PLAIN, input_fn=fake_input, out=out), out, prompts


def _directory(path: Path) -> Path:
    path.write_text(
        "version: 1\nlanguage: es\npeople:\n  - id: ana\n    name: Ana\n"
        "terms:\n  - term: Acme\n  - term: Rappi\n"
    )
    return path


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _directory(tmp_path / "directory.yaml")
    (tmp_path / "saidby.toml").write_text(
        '[saidby]\nlanguage = "es"\n[glossary]\ndirectory = "directory.yaml"\n'
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_the_plan_shows_each_value_and_where_it_comes_from(project: Path) -> None:
    ui, out, prompts = _session([""])
    plan = plan_run(ui, [Path("a.m4a"), Path("b.mp4")], Settings.load())
    assert plan is not None
    assert len(prompts) == 1
    text = out.getvalue()
    assert "Ready to process 2 files" in text
    assert "directory.yaml · 1 person · 2 terms  ./saidby.toml" in text
    assert "language  es  ./saidby.toml" in text
    assert "./saidby/  default" in text
    assert "Enter start   t terms for this recording   e change something   q quit" in text
    assert plan.chosen == {}
    assert plan.added_terms == []


def test_flags_and_the_environment_are_named_as_the_source(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAIDBY_OUT", "results")
    ui, out, _ = _session([""])
    plan_run(ui, INPUTS, Settings.load(overrides={"language": "en", "num_speakers": 3}))
    text = out.getvalue()
    assert "en  command line" in text
    assert "3  command line" in text
    assert "SAIDBY_OUT" in text


def test_the_language_is_asked_only_when_nothing_set_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    ui, out, prompts = _session(["spanish", "ES", ""])
    plan = plan_run(ui, INPUTS, Settings.load())
    assert plan is not None
    assert "Language of the recording?" in prompts[0]
    assert "is not a language code" in out.getvalue()
    assert plan.settings.language == "es"
    assert plan.chosen == {"language": "es"}
    assert "es  chosen just now" in out.getvalue()
    assert len(prompts) == 3


def test_enter_at_the_language_question_leaves_it_to_detection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    ui, out, _ = _session(["", ""])
    plan = plan_run(ui, INPUTS, Settings.load())
    assert plan is not None
    assert plan.settings.language is None
    assert "detect it from the audio" in out.getvalue()


def test_a_set_language_is_not_asked_again(project: Path) -> None:
    ui, _, prompts = _session([""])
    plan_run(ui, INPUTS, Settings.load())
    assert not any("Language of the recording?" in p for p in prompts)


def test_t_adds_terms_for_this_recording_without_duplicates(project: Path) -> None:
    ui, out, _ = _session(["t", "Acme, Zeta , rappi pay, zeta", ""])
    plan = plan_run(ui, INPUTS, Settings.load(overrides={"terms": ["Acme"]}))
    assert plan is not None
    assert plan.added_terms == ["Zeta", "rappi pay"]
    assert plan.settings.terms == ["Acme", "Zeta", "rappi pay"]
    assert "Acme, Zeta, rappi pay  this recording" in out.getvalue()


def test_split_terms_ignores_blanks_and_known_terms() -> None:
    assert split_terms(" a, ,B,, A ", ["b"]) == ["a"]
    assert split_terms("", []) == []


def test_e_changes_each_value_and_refuses_bad_answers(project: Path, tmp_path: Path) -> None:
    other = _directory(tmp_path / "other.yaml")
    ui, out, _ = _session(
        [
            "e", "nothing",
            "language", "pt",
            "e", "glossary", "missing.yaml", str(other),
            "e", "speakers", "zero", "2",
            "e", "output", "results",
            "e", "terms", "Zeta",
            "",
        ]
    )  # fmt: skip
    plan = plan_run(ui, INPUTS, Settings.load())
    assert plan is not None
    settings = plan.settings
    assert (settings.language, settings.num_speakers, settings.out) == ("pt", 2, Path("results"))
    assert settings.directory == [other]
    assert settings.terms == ["Zeta"]
    assert plan.chosen == {
        "language": "pt",
        "directory": str(other),
        "num_speakers": "2",
        "out": "results",
    }
    text = out.getvalue()
    assert "choose one of: language, glossary, speakers, output, terms" in text
    assert "is not a file" in text
    assert "type a number of 1 or more" in text


def test_clearing_the_glossary_leaves_none(project: Path) -> None:
    ui, out, _ = _session(["e", "glossary", "", ""])
    plan = plan_run(ui, INPUTS, Settings.load())
    assert plan is not None
    assert plan.settings.directory == []
    assert plan.chosen["directory"] == ""
    assert "glossary  none" in out.getvalue()


def test_q_runs_nothing_and_an_unknown_key_is_asked_again(project: Path) -> None:
    ui, out, prompts = _session(["x", "q"])
    assert plan_run(ui, INPUTS, Settings.load()) is None
    assert "type Enter, t, e or q" in out.getvalue()
    assert "nothing was run" in out.getvalue()
    assert len(prompts) == 2


def test_a_broken_glossary_is_shown_not_fatal(project: Path) -> None:
    (project / "directory.yaml").write_text("version: 7\n")
    ui, out, _ = _session(["q"])
    plan_run(ui, INPUTS, Settings.load())
    assert "directory.yaml ·" in out.getvalue()


class FakePipeline:
    runs: ClassVar[list[tuple[Settings, list[Path]]]] = []

    def __init__(self, settings: Settings, **_: Any) -> None:
        self.settings = settings

    def run(self, inputs: list[Path], out_root: Path) -> list[Any]:
        FakePipeline.runs.append((self.settings, inputs))
        return []


def test_the_command_needs_a_terminal_and_the_human_progress(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = runner.invoke(app, ["process", "call.m4a", "-i"])
    assert isinstance(result.exception, UsageError)
    assert "needs a terminal; without one, use: saidby process call.m4a" in str(result.exception)
    module = sys.modules["saidby.cli.process"]
    monkeypatch.setattr(module, "ensure_terminal", lambda command: None)
    result = runner.invoke(app, ["process", "call.m4a", "-i", "--progress", "json"])
    assert "-i needs the human progress output" in str(result.exception)


def test_the_command_runs_with_what_the_plan_decided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    FakePipeline.runs = []
    ui, _, _ = _session(["pt", "t", "Acme", ""])
    module = sys.modules["saidby.cli.process"]
    monkeypatch.setattr(module, "ensure_terminal", lambda command: None)
    monkeypatch.setattr(module, "_ui", lambda: ui)
    monkeypatch.setattr(module, "Pipeline", FakePipeline)
    result = runner.invoke(app, ["process", "call.m4a", "-i"])
    assert result.exit_code == 0, result.output
    settings, inputs = FakePipeline.runs[0]
    assert (settings.language, settings.terms) == ("pt", ["Acme"])
    assert inputs == [Path("call.m4a")]


def test_quitting_the_plan_never_builds_the_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    FakePipeline.runs = []
    ui, _, _ = _session(["", "q"])
    module = sys.modules["saidby.cli.process"]
    monkeypatch.setattr(module, "ensure_terminal", lambda command: None)
    monkeypatch.setattr(module, "_ui", lambda: ui)
    monkeypatch.setattr(module, "Pipeline", FakePipeline)
    result = runner.invoke(app, ["process", "call.m4a", "-i"])
    assert result.exit_code == 0, result.output
    assert FakePipeline.runs == []


def test_a_glossary_typed_with_a_tilde_is_stored_as_a_real_path(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    shared = _directory(home / "shared.yaml")
    monkeypatch.setenv("HOME", str(home))
    ui, _, _ = _session(["e", "glossary", "~/shared.yaml", ""])
    plan = plan_run(ui, INPUTS, Settings.load())
    assert plan is not None
    assert plan.settings.directory == [shared]
    assert plan.chosen["directory"] == str(shared)


def test_dropping_the_glossary_is_remembered_as_a_choice(project: Path) -> None:
    ui, _, _ = _session(["e", "glossary", "", ""])
    plan = plan_run(ui, INPUTS, Settings.load())
    assert plan is not None
    assert plan.settings.directory == []
    assert plan.chosen["directory"] == ""


def _on_a_terminal(monkeypatch: pytest.MonkeyPatch, ui: Ui) -> None:
    monkeypatch.setattr("saidby.cli.ui.interactive_streams", lambda: True)
    monkeypatch.setattr(sys.modules["saidby.cli.process"], "_ui", lambda: ui)
    monkeypatch.setattr(sys.modules["saidby.cli.process"], "Pipeline", FakePipeline)


def test_on_a_terminal_the_plan_is_shown_without_any_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    FakePipeline.runs = []
    ui, out, prompts = _session(["es", ""])
    _on_a_terminal(monkeypatch, ui)
    result = runner.invoke(app, ["process", "call.m4a"])
    assert result.exit_code == 0, result.output
    assert "Ready to process 1 file" in out.getvalue()
    assert len(prompts) == 2
    assert FakePipeline.runs[0][0].language == "es"


def test_without_a_terminal_nothing_is_asked_and_the_run_just_happens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    FakePipeline.runs = []
    monkeypatch.setattr(sys.modules["saidby.cli.process"], "Pipeline", FakePipeline)
    result = runner.invoke(app, ["process", "call.m4a"])
    assert result.exit_code == 0, result.output
    assert FakePipeline.runs[0][1] == [Path("call.m4a")]
    assert "Ready to process" not in result.output


@pytest.mark.parametrize(
    ("args", "env"),
    [
        (["--no-interactive"], {}),
        (["--progress", "json"], {}),
        ([], {"SAIDBY_INTERACTIVE": "false"}),
    ],
)
def test_a_flag_the_progress_mode_or_the_setting_turn_the_questions_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str], env: dict[str, str]
) -> None:
    monkeypatch.chdir(tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    FakePipeline.runs = []
    ui, _, prompts = _session([])
    _on_a_terminal(monkeypatch, ui)
    result = runner.invoke(app, ["process", "call.m4a", *args])
    assert result.exit_code == 0, result.output
    assert prompts == []
    assert len(FakePipeline.runs) == 1


def test_a_project_file_can_turn_the_questions_off_and_i_turns_them_back_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "saidby.toml").write_text('[saidby]\nlanguage = "es"\ninteractive = false\n')
    FakePipeline.runs = []
    ui, _, prompts = _session([""])
    _on_a_terminal(monkeypatch, ui)
    assert runner.invoke(app, ["process", "call.m4a"]).exit_code == 0
    assert prompts == []
    assert runner.invoke(app, ["process", "call.m4a", "-i"]).exit_code == 0
    assert len(prompts) == 1
