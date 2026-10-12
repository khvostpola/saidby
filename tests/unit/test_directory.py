# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from saidby.cli import app
from saidby.errors import InputError, UsageError
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


def _sample(tmp_path: Path) -> Path:
    path = tmp_path / "d.yaml"
    path.write_text(SAMPLE)
    return path


def test_add_person_derives_the_id_and_keeps_comments(tmp_path: Path) -> None:
    path = _sample(tmp_path)
    result = runner.invoke(
        app,
        [
            "directory",
            "add-person",
            "Ana María Gómez",
            "--directory",
            str(path),
            "--alias",
            "Anita",
            "--variant",
            "Ana Maria",
            "--context",
            "accountant",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "added ana-maria-gomez (Ana María Gómez)" in result.output
    directory, _ = load_directory(path)
    person = directory.person("ana-maria-gomez")
    assert person is not None
    assert (person.aliases, person.variants, person.context) == (
        ["Anita"],
        ["Ana Maria"],
        "accountant",
    )
    saved = path.read_text()
    assert "# team directory" in saved
    assert "# the owner" in saved
    assert list(tmp_path.glob("d.bak-*.yaml"))


def test_add_person_takes_an_explicit_id_and_refuses_duplicates(tmp_path: Path) -> None:
    path = _sample(tmp_path)
    base = ["directory", "add-person", "--directory", str(path)]
    assert runner.invoke(app, [*base, "Ben", "--id", "ben"]).exit_code == 0
    again = runner.invoke(app, [*base, "Benito", "--id", "ben"])
    assert isinstance(again.exception, UsageError)
    assert "already exists" in str(again.exception)
    same_name = runner.invoke(app, [*base, "ana"])
    assert isinstance(same_name.exception, UsageError)
    assert "p-001" in str(same_name.exception)


def test_add_person_id_gets_a_suffix_when_taken(tmp_path: Path) -> None:
    path = _sample(tmp_path)
    base = ["directory", "add-person", "--directory", str(path)]
    assert runner.invoke(app, [*base, "Ben Ruiz"]).exit_code == 0
    assert runner.invoke(app, [*base, "Ben Ruiz (client)"]).exit_code == 0
    ids = [p.id for p in load_directory(path)[0].people]
    assert ids == ["p-001", "ben-ruiz", "ben-ruiz-client"]


def test_add_person_needs_an_id_when_the_name_has_no_letters(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["directory", "add-person", "李雷", "--directory", str(_sample(tmp_path))]
    )
    assert isinstance(result.exception, UsageError)
    assert "--id" in str(result.exception)


def test_add_term_with_variants_confusions_and_dialect(tmp_path: Path) -> None:
    path = _sample(tmp_path)
    result = runner.invoke(
        app,
        [
            "directory",
            "add-term",
            "Rappi",
            "--directory",
            str(path),
            "--variant",
            "rapi",
            "--confusion",
            "rap",
            "--context",
            "delivery app",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (
        runner.invoke(
            app, ["directory", "add-term", "chimba", "--dialect", "--directory", str(path)]
        ).exit_code
        == 0
    )
    terms = {t.term: t for t in load_directory(path)[0].terms}
    assert (terms["Rappi"].variants, terms["Rappi"].confusions) == (["rapi"], ["rap"])
    assert terms["chimba"].type == "dialect"
    duplicate = runner.invoke(app, ["directory", "add-term", "ACME", "--directory", str(path)])
    assert isinstance(duplicate.exception, UsageError)


def test_edits_go_to_the_last_configured_directory_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = tmp_path / "shared.yaml"
    shared.write_text(SAMPLE)
    project = tmp_path / "project.yaml"
    project.write_text(SAMPLE)
    (tmp_path / "saidby.toml").write_text(f'[glossary]\ndirectory = ["{shared}", "project.yaml"]\n')
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["directory", "add-term", "Rappi"]).exit_code == 0
    assert "Rappi" in project.read_text()
    assert "Rappi" not in shared.read_text()


def test_edits_without_any_directory_say_how_to_fix_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["directory", "add-term", "Rappi"])
    assert isinstance(result.exception, UsageError)
    assert "--directory" in str(result.exception)
