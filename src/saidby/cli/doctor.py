# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import platform
import sys
from typing import Annotated

import typer

from saidby import __version__
from saidby.i18n import _, ngettext, set_language
from saidby.models import REGISTRY
from saidby.models import store as model_store
from saidby.runtime.diagnose import Check, run_checks

SYMBOLS = {"ok": "ok  ", "warn": "warn", "fail": "FAIL"}


def _print(checks: list[Check]) -> None:
    width = max(len(c.name) for c in checks)
    for check in checks:
        typer.echo(f"{SYMBOLS[check.status]}  {check.name.ljust(width)}  {check.detail}")
        if (check.hint and check.status != "ok") or (check.hint and check.name == "device"):
            typer.echo(f"      {' ' * width}  -> {check.hint}")


def doctor(
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output")] = False,
    smoke: Annotated[
        bool, typer.Option("--smoke", help="Also run a short transcription with asr:tiny")
    ] = False,
    device: Annotated[str, typer.Option(help="Device to check: auto, cuda or cpu")] = "auto",
) -> None:
    """Check that this machine can run saidby and say how to fix what is missing."""
    if as_json:
        set_language("en")
    checks = run_checks(smoke=smoke, requested=device)
    failures = [c for c in checks if c.status == "fail"]
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "saidby": __version__,
                    "python": platform.python_version(),
                    "platform": sys.platform,
                    "ffmpeg": next((c.detail for c in checks if c.name == "ffmpeg"), None),
                    "models": {s.key: model_store.is_installed(s) for s in REGISTRY},
                    "checks": [c.__dict__ for c in checks],
                    "problems": [f"{c.name}: {c.detail}" for c in failures],
                },
                indent=2,
            )
        )
    else:
        typer.echo(_("saidby {version}").format(version=__version__))
        _print(checks)
        typer.echo("")
        if failures:
            problems = ngettext(
                "{n} problem to fix before processing",
                "{n} problems to fix before processing",
                len(failures),
            )
            typer.echo(problems.format(n=len(failures)))
        else:
            typer.echo(_("ready"))
    raise typer.Exit(1 if failures else 0)
