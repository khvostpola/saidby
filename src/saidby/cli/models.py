# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
from typing import Annotated

import typer

from saidby.errors import ModelUnavailableError
from saidby.models import REGISTRY, get_spec
from saidby.models import store as model_store
from saidby.runtime import prepare

app = typer.Typer(help="List, download and locate models.", no_args_is_help=True)


def _size_label(size: int | None) -> str:
    if size is None:
        return "-"
    return f"{size / 1e9:.1f} GB" if size >= 1e8 else f"{size / 1e6:.0f} MB"


@app.command("list")
def list_models() -> None:
    """Show every known model and whether it is installed."""
    rows = [("KEY", "REVISION", "INSTALLED", "SIZE", "LICENSE", "GATED", "DEFAULT")]
    for s in REGISTRY:
        rows.append(
            (
                s.key,
                s.revision[:8],
                "yes" if model_store.is_installed(s) else "no",
                _size_label(model_store.size_bytes(s)),
                s.license_spdx,
                "yes" if s.gated else "no",
                "yes" if s.default else "no",
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for row in rows:
        typer.echo("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())


@app.command("licenses")
def licenses() -> None:
    """Show the license and attribution of every model."""
    for s in REGISTRY:
        typer.echo(f"{s.key}: {s.license_spdx} · {s.repo_id}@{s.revision[:8]} · {s.attribution}")
        typer.echo(f"  {s.url}")


@app.command("path")
def path(key: Annotated[str, typer.Argument(help="Model key, e.g. asr:large-v3")]) -> None:
    """Print the local snapshot path of an installed model."""
    typer.echo(str(model_store.local_path(get_spec(key))))


@app.command("pull")
def pull(
    keys: Annotated[list[str] | None, typer.Argument(help="Model keys to download")] = None,
    all_defaults: Annotated[bool, typer.Option("--all", help="Pull every default model")] = False,
    token: Annotated[str | None, typer.Option(help="Hugging Face token")] = None,
    allow_noncommercial: Annotated[
        bool,
        typer.Option(
            "--allow-noncommercial", help="Also pull models that are not for commercial use."
        ),
    ] = False,
) -> None:
    """Download models. This is the only command that uses the network."""
    prepare(offline=False, want_cuda=False)
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)
    specs = (
        [s for s in REGISTRY if s.default] if all_defaults else [get_spec(k) for k in keys or []]
    )
    if not specs:
        raise typer.BadParameter("give at least one model key or --all")
    for spec in specs:
        if not spec.commercial_ok and not allow_noncommercial:
            raise ModelUnavailableError(
                f"{spec.key} is not licensed for commercial use; "
                "pass --allow-noncommercial to pull it"
            )
        target = model_store.pull(spec, token=token or os.environ.get("HF_TOKEN"))
        typer.echo(f"{spec.key}: {target}")
