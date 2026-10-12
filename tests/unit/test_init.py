# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import sys
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from saidby.cli import app
from saidby.config.settings import Settings
from saidby.config.writer import check_language, default_language, update_config
from saidby.errors import UsageError
from saidby.formats.directory_yaml import load_directory

runner = CliRunner()


def test_init_creates_a_folder_that_needs_no_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--yes", "--language", "es"])
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "consent.yaml",
        "directory.yaml",
        "saidby.toml",
    ]
    settings = Settings.load()
    assert settings.language == "es"
    assert settings.out == tmp_path / "saidby"
    assert settings.directory == [tmp_path / "directory.yaml"]
    assert settings.sources == [tmp_path / "saidby.toml"]
    directory, _ = load_directory(tmp_path / "directory.yaml")
    assert (directory.language, directory.people, directory.terms) == ("es", [], [])


def test_the_starter_directory_takes_people_and_terms_in_block_style(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init", "--yes", "--language", "es"]).exit_code == 0
    assert runner.invoke(app, ["directory", "add-person", "Ana Gómez"]).exit_code == 0
    assert runner.invoke(app, ["directory", "add-term", "Acme"]).exit_code == 0
    text = (tmp_path / "directory.yaml").read_text()
    assert "[" not in text
    assert "# People whose voices you want named" in text
    directory, _ = load_directory(tmp_path / "directory.yaml")
    assert [p.id for p in directory.people] == ["ana-gomez"]
    assert [t.term for t in directory.terms] == ["Acme"]


def test_init_never_overwrites_existing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "saidby.toml").write_text('[saidby]\nlanguage = "pt"\n')
    result = runner.invoke(app, ["init", "--yes", "--language", "es"])
    assert result.exit_code == 0, result.output
    assert "kept   saidby.toml" in result.output
    assert (tmp_path / "saidby.toml").read_text() == '[saidby]\nlanguage = "pt"\n'
    assert (tmp_path / "directory.yaml").is_file()


def test_init_global_writes_the_user_config_folder(
    tmp_path: Path, isolated_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init", "--global", "--yes", "--language", "en"]).exit_code == 0
    folder = isolated_user_config / "config" / "saidby"
    assert sorted(p.name for p in folder.iterdir()) == [
        "config.toml",
        "consent.yaml",
        "directory.yaml",
    ]
    assert "out" not in (folder / "config.toml").read_text()
    settings = Settings.load()
    assert settings.language == "en"
    assert settings.directory == [folder / "directory.yaml"]
    assert not list(tmp_path.iterdir())


def test_init_asks_for_the_language_and_the_global_glossary(
    tmp_path: Path, isolated_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = isolated_user_config / "config" / "saidby" / "directory.yaml"
    shared.parent.mkdir(parents=True)
    shared.write_text("version: 1\nlanguage: es\n")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setattr(sys.modules["saidby.cli.init"], "_interactive", lambda: True)
    result = runner.invoke(app, ["init"], input="pt\ny\n")
    assert result.exit_code == 0, result.output
    settings = Settings.load()
    assert settings.language == "pt"
    assert settings.directory == [shared, work / "directory.yaml"]


def test_declining_the_global_glossary_leaves_it_out(
    tmp_path: Path, isolated_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = isolated_user_config / "config" / "saidby" / "directory.yaml"
    shared.parent.mkdir(parents=True)
    shared.write_text("version: 1\nlanguage: es\n")
    (shared.parent / "config.toml").write_text('[glossary]\ndirectory = ["directory.yaml"]\n')
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setattr(sys.modules["saidby.cli.init"], "_interactive", lambda: True)
    assert runner.invoke(app, ["init"], input="es\nn\n").exit_code == 0
    assert Settings.load().directory == [work / "directory.yaml"]


def test_a_bad_language_code_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--yes", "--language", "not a code"])
    assert isinstance(result.exception, UsageError)
    assert not list(tmp_path.iterdir())
    assert check_language("PT-br") == "pt-br"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("es_CO.UTF-8", "es"), ("pt_BR", "pt"), ("en_US.UTF-8", "en"), ("fr", "fr")],
)
def test_default_language_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: str
) -> None:
    for name in ("LC_ALL", "LC_MESSAGES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANG", value)
    assert default_language() == expected


def test_update_config_creates_a_file_with_only_what_it_was_given(tmp_path: Path) -> None:
    path = tmp_path / "saidby.toml"
    assert update_config(path, language="es", out="results", directory=["directory.yaml"]) is None
    assert tomllib.loads(path.read_text()) == {
        "saidby": {"language": "es", "out": "results"},
        "glossary": {"directory": ["directory.yaml"]},
    }


def test_update_config_keeps_comments_and_other_keys_and_makes_a_backup(tmp_path: Path) -> None:
    path = tmp_path / "saidby.toml"
    path.write_text(
        '# my settings\n[saidby]\nlanguage = "en"  # english\ndevice = "cpu"\n'
        '[asr]\nmodel = "tiny"\n[glossary]\ndirectory = "old.yaml"\nbias = false\n'
    )
    backup = update_config(path, language="es", directory=["a.yaml", "b.yaml"])
    assert backup is not None
    assert backup.read_text().startswith("# my settings")
    text = path.read_text()
    assert "# my settings" in text
    assert 'language = "es"' in text
    assert tomllib.loads(text) == {
        "saidby": {"language": "es", "device": "cpu"},
        "asr": {"model": "tiny"},
        "glossary": {"directory": ["a.yaml", "b.yaml"], "bias": False},
    }


def test_update_config_leaves_untouched_what_it_was_not_given(tmp_path: Path) -> None:
    path = tmp_path / "saidby.toml"
    path.write_text('[saidby]\nlanguage = "pt"\n')
    update_config(path, out="results")
    assert tomllib.loads(path.read_text()) == {"saidby": {"language": "pt", "out": "results"}}
