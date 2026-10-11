# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from saidby.cli import app
from saidby.errors import InputError
from saidby.formats.directory_yaml import load_directory, save_directory
from saidby.schema.directory import Directory

runner = CliRunner()

SAMPLE = """# team directory
version: 1
language: es
people:
  # the owner
  - id: p-001
    name: Ana
    variants: [Anna]
terms:
  - term: Acme
    variants: [akme]
  - term: parce
    type: dialect
    variants: [parse]
"""


def test_valid_directory_loads(tmp_path: Path) -> None:
    path = tmp_path / "d.yaml"
    path.write_text(SAMPLE)
    directory, _ = load_directory(path)
    assert directory.people[0].id == "p-001"
    assert directory.terms[1].type == "dialect"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["people"].append({"id": "p-001", "name": "Dup"}),
        lambda d: d["people"].append({"id": "Bad Id", "name": "X"}),
        lambda d: d.update(version=2),
        lambda d: d["terms"].append({"term": "acme"}),
        lambda d: d["people"][0].update(surprise=1),
    ],
)
def test_invalid_directories_are_rejected(tmp_path: Path, mutation: object) -> None:
    import yaml

    data = yaml.safe_load(SAMPLE)
    mutation(data)  # type: ignore[operator]
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(InputError):
        load_directory(path)


def test_save_keeps_comments_and_makes_backup(tmp_path: Path) -> None:
    path = tmp_path / "d.yaml"
    path.write_text(SAMPLE)
    _, raw = load_directory(path)
    raw["people"][0]["context"] = "owner"
    backup = save_directory(path, raw)
    assert backup is not None
    assert backup.read_text() == SAMPLE
    saved = path.read_text()
    assert "# team directory" in saved
    assert "# the owner" in saved
    assert "context: owner" in saved


def test_cli_validate_schema_and_init(tmp_path: Path) -> None:
    path = tmp_path / "d.yaml"
    assert runner.invoke(app, ["directory", "init", str(path)]).exit_code == 0
    assert runner.invoke(app, ["directory", "validate", str(path)]).exit_code == 0
    assert runner.invoke(app, ["directory", "init", str(path)]).exit_code != 0
    schema = json.loads(runner.invoke(app, ["directory", "schema"]).stdout)
    assert schema == Directory.model_json_schema()
