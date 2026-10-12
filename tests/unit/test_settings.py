# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

from saidby.config.settings import Settings
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
    assert settings.directory == tmp_path / "team/directory.yaml"
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
