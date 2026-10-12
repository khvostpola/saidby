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
    display_path,
    portable_path,
    render_config,
)
from saidby.formats.directory_set import CONSENT_FILE
from saidby.i18n import _


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stderr.isatty()


def _write_new(path: Path, text: str, note: str) -> None:
    if path.exists():
        typer.echo(_("  kept   {name:<16} already there, not touched").format(name=path.name))
        return
    path.write_text(text, encoding="utf-8", newline="\n")
    typer.echo(_("  wrote  {name:<16} {note}").format(name=path.name, note=note))


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
        typer.Option(
            "--global",
            help="Set up the user config folder for every folder, not this one "
            "(~/.config/saidby on Linux, %APPDATA%\\saidby on Windows).",
        ),
    ] = False,
) -> None:
    """Create saidby.toml, directory.yaml and consent.yaml, so the next run needs no flags."""
    ask = _interactive() and not yes
    chosen = language or default_language()
    if ask and language is None:
        chosen = typer.prompt(_("Language of your recordings"), default=chosen)
    chosen = check_language(chosen)
    folder = global_config_path().parent if global_ else Path.cwd()
    shared = global_config_path().parent / "directory.yaml"
    directories = ["directory.yaml"]
    if not global_ and shared.is_file():
        use_shared = True
        if ask:
            use_shared = typer.confirm(
                _("Use the global glossary {shorten_home} here too?").format(
                    shorten_home=display_path(shared)
                ),
                default=True,
            )
        if use_shared:
            directories.insert(0, portable_path(shared))
    folder.mkdir(parents=True, exist_ok=True)
    config = folder / ("config.toml" if global_ else "saidby.toml")
    typer.echo(_("Setting up {folder}").format(folder=folder))
    config_note = _("language {language}").format(language=chosen)
    if not global_:
        config_note += " · " + _("output ./saidby/")
    _write_new(
        config,
        render_config(language=chosen, directories=directories, out=None if global_ else "saidby"),
        f"{config_note} · " + _("glossary {files}").format(files=", ".join(directories)),
    )
    starter = DIRECTORY_STARTER.format(language=chosen)
    _write_new(folder / "directory.yaml", starter, _("empty, with hints"))
    _write_new(folder / CONSENT_FILE, CONSENT_STARTER, _("empty"))
    where = _("every folder") if global_ else _("this folder")
    typer.echo(
        _("Done. In {where}, `saidby process call.m4a` needs no flags now.").format(where=where)
    )
