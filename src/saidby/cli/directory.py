# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
from typing import Annotated

import typer

from saidby.config.settings import Settings, global_config_path
from saidby.errors import UsageError
from saidby.formats.directory_edit import add_person, add_term
from saidby.formats.directory_yaml import load_directory, save_directory
from saidby.i18n import _, ngettext
from saidby.schema.directory import Directory
from saidby.speakers.naming import ascii_slug, person_id_for

app = typer.Typer(help="Validate, create and edit directory files.", no_args_is_help=True)

TARGET_HELP = "Directory file to edit (default: the last configured one)."

TEMPLATE = """version: 1
language: {language}
people:
  - id: example-person
    name: Example Person
    variants: []
    context: role or relation, optional
terms:
  - term: ExampleTerm
    variants: [example term]
    confusions: []
    context: what it means, optional
"""


@app.command("validate")
def validate(
    file: Annotated[Path, typer.Argument(help="Directory YAML file to check.")],
) -> None:
    """Check a directory file against the schema."""
    directory, _raw = load_directory(file)
    people = ngettext("{n} person", "{n} people", len(directory.people))
    terms = ngettext("{n} term", "{n} terms", len(directory.terms))
    typer.echo(
        _("ok: {people}, {terms}").format(
            people=people.format(n=len(directory.people)),
            terms=terms.format(n=len(directory.terms)),
        )
    )


@app.command("schema")
def schema() -> None:
    """Print the JSON Schema of the directory format."""
    typer.echo(json.dumps(Directory.model_json_schema(), indent=2))


@app.command("init")
def init(
    file: Annotated[
        Path | None, typer.Argument(help="Where to create the starter directory.")
    ] = None,
    language: Annotated[str, typer.Option(help="Recording language")] = "es",
    global_: Annotated[
        bool,
        typer.Option("--global", help="Create it in ~/.config/saidby/, shared by every folder."),
    ] = False,
) -> None:
    """Create a starter directory file."""
    if file is None and not global_:
        raise UsageError(_("give a file name, or use --global"))
    target = file or global_config_path().parent / "directory.yaml"
    if target.exists():
        raise UsageError(_("{target} already exists").format(target=target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(TEMPLATE.format(language=language), encoding="utf-8")
    typer.echo(_("created {target}").format(target=target))


def _target(directory: Path | None) -> Path:
    if directory is not None:
        return directory
    configured = Settings.load().directory
    if not configured:
        raise UsageError(_("no directory file: pass --directory or set one in saidby.toml"))
    return configured[-1]


@app.command("add-person")
def add_person_command(
    name: Annotated[str, typer.Argument(help="The person's name as it should be written.")],
    person_id: Annotated[
        str | None, typer.Option("--id", help="Id for the person (default: made from the name).")
    ] = None,
    aliases: Annotated[
        list[str] | None, typer.Option("--alias", help="Other name they go by; repeatable.")
    ] = None,
    variants: Annotated[
        list[str] | None,
        typer.Option("--variant", help="A misspelling the recognizer makes; repeatable."),
    ] = None,
    context: Annotated[str | None, typer.Option(help="Role or relation, optional.")] = None,
    directory: Annotated[Path | None, typer.Option(help=TARGET_HELP)] = None,
) -> None:
    """Add a person to a directory file, keeping its comments."""
    file = _target(directory)
    _model, raw = load_directory(file)
    if person_id is None and not ascii_slug(name):
        raise UsageError(_("cannot make an id from that name; pass --id"))
    taken = [p["id"] for p in raw.get("people") or []]
    chosen = person_id or person_id_for(name, taken)
    add_person(
        raw,
        person_id=chosen,
        name=name,
        aliases=aliases or (),
        variants=variants or (),
        context=context,
    )
    backup = save_directory(file, raw)
    if backup:
        message = _("added {chosen} ({name}) to {file} (backup: {backup})")
    else:
        message = _("added {chosen} ({name}) to {file}")
    typer.echo(message.format(chosen=chosen, name=name, file=file, backup=backup))


@app.command("add-term")
def add_term_command(
    term: Annotated[str, typer.Argument(help="The term, spelled the way it should be written.")],
    variants: Annotated[
        list[str] | None,
        typer.Option("--variant", help="A misspelling the recognizer makes; repeatable."),
    ] = None,
    confusions: Annotated[
        list[str] | None,
        typer.Option("--confusion", help="A real word it gets mistaken for; repeatable."),
    ] = None,
    context: Annotated[str | None, typer.Option(help="What it means, optional.")] = None,
    dialect: Annotated[
        bool, typer.Option("--dialect", help="Regional slang with one canonical spelling.")
    ] = False,
    directory: Annotated[Path | None, typer.Option(help=TARGET_HELP)] = None,
) -> None:
    """Add a term to a directory file, keeping its comments."""
    file = _target(directory)
    _model, raw = load_directory(file)
    add_term(
        raw,
        term=term,
        variants=variants or (),
        confusions=confusions or (),
        context=context,
        dialect=dialect,
    )
    backup = save_directory(file, raw)
    if backup:
        message = _("added {term} to {file} (backup: {backup})")
    else:
        message = _("added {term} to {file}")
    typer.echo(message.format(term=term, file=file, backup=backup))
