# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typer.testing import CliRunner

from saidby.cli import app

runner = CliRunner()


def test_models_list_shows_every_key() -> None:
    result = runner.invoke(app, ["models", "list"])
    assert result.exit_code == 0
    assert "asr:large-v3" in result.stdout
    assert "diarizer:nemotron3" in result.stdout


def test_models_licenses() -> None:
    result = runner.invoke(app, ["models", "licenses"])
    assert result.exit_code == 0
    assert "OpenMDW-1.1" in result.stdout


def test_models_pull_requires_keys() -> None:
    result = runner.invoke(app, ["models", "pull"])
    assert result.exit_code != 0


def test_doctor_json_is_valid() -> None:
    import json

    result = runner.invoke(app, ["doctor", "--json"])
    report = json.loads(result.stdout)
    assert {"saidby", "ffmpeg", "models", "problems"} <= report.keys()
