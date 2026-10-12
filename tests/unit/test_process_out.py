# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path
from typing import Any, ClassVar

import pytest
from typer.testing import CliRunner

from saidby.cli import app
from saidby.config.settings import Settings

runner = CliRunner()


class _RecordingPipeline:
    runs: ClassVar[list[tuple[list[Path], Path]]] = []
    settings_seen: ClassVar[list[Settings]] = []

    def __init__(self, settings: Settings, **_: Any) -> None:
        self.settings = settings
        self.settings_seen.append(settings)

    def run(self, inputs: list[Path], out: Path) -> list[Any]:
        self.runs.append((inputs, out))
        return []


@pytest.fixture(autouse=True)
def recording(monkeypatch: pytest.MonkeyPatch) -> type[_RecordingPipeline]:
    _RecordingPipeline.runs = []
    _RecordingPipeline.settings_seen = []
    monkeypatch.setattr(sys.modules["saidby.cli.process"], "Pipeline", _RecordingPipeline)
    return _RecordingPipeline


def _output_folder(recording: type[_RecordingPipeline]) -> Path:
    assert len(recording.runs) == 1
    return recording.runs[0][1]


def test_out_defaults_to_a_saidby_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording: type[_RecordingPipeline]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["process", "call.m4a"]).exit_code == 0
    assert _output_folder(recording) == Path("saidby")


def test_out_flag_wins_over_the_project_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording: type[_RecordingPipeline]
) -> None:
    (tmp_path / "saidby.toml").write_text('[saidby]\nout = "results"\n')
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["process", "call.m4a", "--out", "elsewhere"]).exit_code == 0
    assert _output_folder(recording) == Path("elsewhere")


def test_out_from_the_project_file_is_relative_to_that_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording: type[_RecordingPipeline]
) -> None:
    (tmp_path / "saidby.toml").write_text('[saidby]\nout = "results"\n')
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["process", "call.m4a"]).exit_code == 0
    assert _output_folder(recording) == tmp_path / "results"


def test_out_from_the_global_file_stays_relative_to_the_current_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_user_config: Path,
    recording: type[_RecordingPipeline],
) -> None:
    config = isolated_user_config / "config" / "saidby" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text('[saidby]\nout = "results"\n')
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["process", "call.m4a"]).exit_code == 0
    assert _output_folder(recording) == Path("results")


def test_out_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording: type[_RecordingPipeline]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SAIDBY_OUT", "from-env")
    assert runner.invoke(app, ["process", "call.m4a"]).exit_code == 0
    assert _output_folder(recording) == Path("from-env")


def test_directory_flag_is_repeatable_and_replaces_the_configured_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording: type[_RecordingPipeline]
) -> None:
    (tmp_path / "saidby.toml").write_text('[glossary]\ndirectory = "from-config.yaml"\n')
    monkeypatch.chdir(tmp_path)
    args = ["process", "call.m4a", "--directory", "a.yaml", "--directory", "b.yaml"]
    assert runner.invoke(app, args).exit_code == 0
    assert recording.settings_seen[0].directory == [Path("a.yaml"), Path("b.yaml")]


def test_directory_comes_from_the_project_file_without_the_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording: type[_RecordingPipeline]
) -> None:
    (tmp_path / "saidby.toml").write_text('[glossary]\ndirectory = "from-config.yaml"\n')
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["process", "call.m4a"]).exit_code == 0
    assert recording.settings_seen[0].directory == [tmp_path / "from-config.yaml"]


def test_term_flag_is_repeatable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recording: type[_RecordingPipeline]
) -> None:
    monkeypatch.chdir(tmp_path)
    args = ["process", "call.m4a", "--term", "Acme", "--term", "Rappi Pay"]
    assert runner.invoke(app, args).exit_code == 0
    assert recording.settings_seen[0].terms == ["Acme", "Rappi Pay"]


def test_process_shows_the_compact_banner_unless_progress_is_for_machines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shown: list[tuple[int, Path]] = []
    monkeypatch.setattr(
        sys.modules["saidby.cli.process"], "show_compact", lambda n, out: shown.append((n, out))
    )
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["process", "a.m4a", "b.m4a"]).exit_code == 0
    assert shown == [(2, Path("saidby"))]
    for mode in ("json", "none"):
        assert runner.invoke(app, ["process", "a.m4a", "--progress", mode]).exit_code == 0
    assert len(shown) == 1
