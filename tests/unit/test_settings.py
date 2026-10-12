# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path

import pytest

from saidby.config.settings import Settings, find_project_config, global_config_path
from saidby.errors import UsageError


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "saidby.toml"
    path.write_text(body)
    return path


def test_documented_file_loads_and_resolves_relative_directory(tmp_path: Path) -> None:
    config = _write(
        tmp_path,
        """
[saidby]
device = "cpu"
language = "es"
keep_intermediates = true

[asr]
model = "tiny"
compute_type = "int8"
deterministic = true

[diarizer]
engine = "nemotron3"
num_speakers = 2

[glossary]
directory = "team/directory.yaml"
bias_mode = "windows"
correct = true

[llm]
url = "http://127.0.0.1:8089"
allow_remote = false
""",
    )
    settings = Settings.load(config)
    assert (settings.device, settings.language, settings.keep_intermediates) == ("cpu", "es", True)
    assert (settings.asr_model, settings.compute_type, settings.deterministic) == (
        "tiny",
        "int8",
        True,
    )
    assert (settings.diarizer, settings.num_speakers) == ("nemotron3", 2)
    assert settings.directory == [tmp_path / "team/directory.yaml"]
    assert (settings.bias_mode, settings.correct, settings.llm_url) == (
        "windows",
        True,
        "http://127.0.0.1:8089",
    )


def test_precedence_command_line_over_env_over_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(tmp_path, '[saidby]\nlanguage = "es"\ndevice = "cpu"\n')
    monkeypatch.setenv("SAIDBY_LANGUAGE", "en")
    monkeypatch.setenv("SAIDBY_DETERMINISTIC", "true")
    settings = Settings.load(config, {"device": "auto", "language": None})
    assert settings.language == "en"
    assert settings.device == "auto"
    assert settings.deterministic is True


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("[asr]\nspeed = 1\n", r"unknown key\(s\) in \[asr\]: speed"),
        ("[saidby]\nlanguge = 'es'\n", r"unknown key\(s\) in \[saidby\]: languge"),
        ("[nonsense]\na = 1\n", r"unknown section \[nonsense\]"),
        ("[saidby]\ndevice = 'tpu'\n", r"invalid configuration: device"),
        ("this is not toml", "not valid TOML"),
    ],
)
def test_bad_files_explain_themselves(tmp_path: Path, body: str, message: str) -> None:
    with pytest.raises(UsageError, match=message):
        Settings.load(_write(tmp_path, body))


def test_missing_explicit_file(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="not found"):
        Settings.load(tmp_path / "nope.toml")


def test_suite_never_reads_the_real_user_config(isolated_user_config: Path) -> None:
    assert os.environ["XDG_CONFIG_HOME"] == str(isolated_user_config / "config")
    assert not [key for key in os.environ if key.startswith("SAIDBY_")]


def _global_config(home: Path, body: str) -> Path:
    path = home / "config" / "saidby" / "config.toml"
    path.parent.mkdir(parents=True)
    path.write_text(body)
    return path


def test_global_and_project_files_merge_key_by_key(
    tmp_path: Path, isolated_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    global_file = _global_config(
        isolated_user_config, '[saidby]\nlanguage = "es"\ndevice = "cpu"\n[asr]\nmodel = "tiny"\n'
    )
    project = tmp_path / "work"
    project.mkdir()
    project_file = _write(project, '[saidby]\ndevice = "cuda"\n')
    monkeypatch.chdir(project)
    settings = Settings.load()
    assert (settings.language, settings.device, settings.asr_model) == ("es", "cuda", "tiny")
    assert settings.sources == [global_file, project_file.resolve()]


def test_explicit_config_ignores_the_global_file(
    tmp_path: Path, isolated_user_config: Path
) -> None:
    _global_config(isolated_user_config, '[saidby]\nlanguage = "es"\n')
    settings = Settings.load(_write(tmp_path, '[saidby]\ndevice = "cpu"\n'))
    assert settings.language is None
    assert len(settings.sources) == 1


def test_no_config_files_means_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings.load()
    assert settings.sources == []
    assert settings.language is None


def test_empty_xdg_config_home_falls_back_to_dot_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert global_config_path() == tmp_path / ".config" / "saidby" / "config.toml"


def test_project_file_is_found_walking_up_inside_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "clients" / "acme"
    deep = project / "recordings" / "2026"
    deep.mkdir(parents=True)
    config = _write(project, '[saidby]\nlanguage = "es"\n')
    assert find_project_config(deep) == config.resolve()


def test_walk_up_stops_at_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    work = home / "work"
    work.mkdir(parents=True)
    _write(tmp_path, '[saidby]\nlanguage = "es"\n')
    monkeypatch.setenv("HOME", str(home))
    assert find_project_config(work) is None


def test_outside_home_only_the_current_folder_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    elsewhere = tmp_path / "elsewhere"
    nested = elsewhere / "nested"
    nested.mkdir(parents=True)
    config = _write(elsewhere, '[saidby]\nlanguage = "es"\n')
    assert find_project_config(nested) is None
    assert find_project_config(elsewhere) == config.resolve()


def test_directory_accepts_a_path_or_a_list_resolved_against_each_file(tmp_path: Path) -> None:
    one = _write(tmp_path, '[glossary]\ndirectory = "a.yaml"\n')
    assert Settings.load(one).directory == [tmp_path / "a.yaml"]
    many = _write(tmp_path, '[glossary]\ndirectory = ["a.yaml", "/abs/b.yaml"]\n')
    assert Settings.load(many).directory == [tmp_path / "a.yaml", Path("/abs/b.yaml")]


def test_directory_must_be_text(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="directory must be a path or a list of paths"):
        Settings.load(_write(tmp_path, "[glossary]\ndirectory = [1]\n"))


def test_directories_from_global_and_project_are_combined_far_to_near(
    tmp_path: Path, isolated_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _global_config(
        isolated_user_config, '[glossary]\ndirectory = ["/shared/team.yaml", "/shared/me.yaml"]\n'
    )
    project = tmp_path / "work"
    project.mkdir()
    _write(project, '[glossary]\ndirectory = ["/shared/me.yaml", "client.yaml"]\n')
    monkeypatch.chdir(project)
    assert Settings.load().directory == [
        Path("/shared/team.yaml"),
        Path("/shared/me.yaml"),
        project.resolve() / "client.yaml",
    ]


def test_directories_from_the_environment_split_on_the_path_separator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAIDBY_DIRECTORY", os.pathsep.join(["/a.yaml", "", "/b.yaml"]))
    assert Settings.load().directory == [Path("/a.yaml"), Path("/b.yaml")]


def test_command_line_directories_replace_the_configured_ones(tmp_path: Path) -> None:
    config = _write(tmp_path, '[glossary]\ndirectory = "a.yaml"\n')
    settings = Settings.load(config, {"directory": [Path("/x.yaml"), Path("/y.yaml")]})
    assert settings.directory == [Path("/x.yaml"), Path("/y.yaml")]


def test_terms_come_from_the_file_or_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(tmp_path, '[glossary]\nterms = ["Acme", "Rappi Pay"]\n')
    assert Settings.load(config).terms == ["Acme", "Rappi Pay"]
    monkeypatch.setenv("SAIDBY_TERMS", " Acme, ,Rappi Pay ")
    assert Settings.load().terms == ["Acme", "Rappi Pay"]
