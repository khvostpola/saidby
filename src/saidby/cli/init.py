# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path
from typing import Annotated

import typer

from saidby.config.settings import global_config_path
from saidby.config.writer import (
    CONSENT_STARTER,
    DIRECTORY_STARTER,
    check_language,
    default_language,
    render_config,
    shorten_home,
)
from saidby.formats.directory_set import CONSENT_FILE


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stderr.isatty()


def _write_new(path: Path, text: str, note: str) -> None:
    if path.exists():
        typer.echo(f"  kept   {path.name:<16} already there, not touched")
        return
    path.write_text(text, encoding="utf-8")
    typer.echo(f"  wrote  {path.name:<16} {note}")


def init(
    language: Annotated[
        str | None,
        typer.Option(help="Language of your recordings, such as es or en (default: asks)."),
    ] = None,
    yes: Annotated[
        bool, typer.Option("--yes", help="Do not ask: take the language option or the default.")
    ] = False,
    global_: Annotated[
        bool,
        typer.Option("--global", help="Set up ~/.config/saidby for every folder, not this one."),
    ] = False,
) -> None:
    """Create saidby.toml, directory.yaml and consent.yaml, so the next run needs no flags."""
    ask = _interactive() and not yes
    chosen = language or default_language()
    if ask and language is None:
        chosen = typer.prompt("Language of your recordings", default=chosen)
    chosen = check_language(chosen)
    folder = global_config_path().parent if global_ else Path.cwd()
    shared = global_config_path().parent / "directory.yaml"
    directories = ["directory.yaml"]
    if not global_ and shared.is_file():
        use_shared = True
        if ask:
            use_shared = typer.confirm(
                f"Use the global glossary {shorten_home(shared)} here too?", default=True
            )
        if use_shared:
            directories.insert(0, shorten_home(shared))
    folder.mkdir(parents=True, exist_ok=True)
    config = folder / ("config.toml" if global_ else "saidby.toml")
    typer.echo(f"Setting up {folder}")
    config_note = f"language {chosen}" + ("" if global_ else " · output ./saidby/")
    _write_new(
        config,
        render_config(language=chosen, directories=directories, out=None if global_ else "saidby"),
        f"{config_note} · glossary {', '.join(directories)}",
    )
    starter = DIRECTORY_STARTER.format(language=chosen)
    _write_new(folder / "directory.yaml", starter, "empty, with hints")
    _write_new(folder / CONSENT_FILE, CONSENT_STARTER, "empty")
    where = "every folder" if global_ else "this folder"
    typer.echo(f"Done. In {where}, `saidby process call.m4a` needs no flags now.")
