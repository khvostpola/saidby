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


def test_init_global_creates_the_shared_directory(
    tmp_path: Path, isolated_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["directory", "init", "--global", "--language", "en"]).exit_code == 0
    shared = isolated_user_config / "config" / "saidby" / "directory.yaml"
    assert load_directory(shared)[0].language == "en"
    assert runner.invoke(app, ["directory", "init", "--global"]).exit_code != 0
    assert isinstance(runner.invoke(app, ["directory", "init"]).exception, UsageError)


INDENTED = """version: 1
language: es
people:
  - id: ana
    name: Ana
terms:
  - term: Acme
    variants:
      - akme
"""
FLUSH = """version: 1
language: es
people:
- id: ana
  name: Ana
"""


def test_saving_keeps_the_list_indentation_the_file_already_uses(tmp_path: Path) -> None:
    for text, marker in ((INDENTED, "\n  - id: ana\n"), (FLUSH, "\n- id: ana\n")):
        path = tmp_path / f"d{len(text)}.yaml"
        path.write_text(text)
        _, raw = load_directory(path)
        raw["people"].append({"id": "ben", "name": "Ben"})
        save_directory(path, raw)
        saved = path.read_text()
        assert marker in saved
        assert saved.count("- id:") == 2


def test_a_file_that_is_new_to_lists_defaults_to_the_documented_style(tmp_path: Path) -> None:
    path = tmp_path / "d.yaml"
    path.write_text("version: 1\nlanguage: es\n# nothing yet\n")
    _, raw = load_directory(path)
    raw["people"] = [{"id": "ana", "name": "Ana"}]
    save_directory(path, raw)
    assert "\npeople:\n  - id: ana\n    name: Ana\n" in path.read_text()


def test_a_root_list_such_as_consent_stays_flush_left(tmp_path: Path) -> None:
    from saidby.formats.consent_yaml import append_consent, load_consents
    from saidby.schema.directory import ConsentRecord

    path = tmp_path / "consent.yaml"
    path.write_text("# consent records\n")
    records, raw = load_consents(path)
    assert records == []
    record = ConsentRecord(person="ana", source="form", declared_by="Ana", date="2026-10-12")  # type: ignore[arg-type]
    append_consent(path, raw, record)
    assert path.read_text().startswith("- person: ana\n")
    records, raw = load_consents(path)
    append_consent(path, raw, record.model_copy(update={"person": "ben"}))
    assert path.read_text().count("\n- person:") == 1
    assert path.read_text().startswith("- person: ana\n")
