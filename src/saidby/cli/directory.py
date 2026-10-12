# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
from typing import Annotated

import typer

from saidby.errors import UsageError
from saidby.formats.directory_yaml import load_directory
from saidby.schema.directory import Directory

app = typer.Typer(help="Validate and create directory files.", no_args_is_help=True)

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
    directory, _ = load_directory(file)
    typer.echo(f"ok: {len(directory.people)} people, {len(directory.terms)} terms")


@app.command("schema")
def schema() -> None:
    """Print the JSON Schema of the directory format."""
    typer.echo(json.dumps(Directory.model_json_schema(), indent=2))


@app.command("init")
def init(
    file: Annotated[Path, typer.Argument(help="Where to create the starter directory.")],
    language: Annotated[str, typer.Option(help="Recording language")] = "es",
) -> None:
    """Create a starter directory file."""
    if file.exists():
        raise UsageError(f"{file} already exists")
    file.write_text(TEMPLATE.format(language=language), encoding="utf-8")
    typer.echo(f"created {file}")
