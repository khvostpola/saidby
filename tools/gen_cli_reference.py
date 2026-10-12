# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import inspect
from pathlib import Path
from typing import Any

import typer.main

from saidby.cli import app

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "cli-reference.md"
SKIP = {"--install-completion", "--show-completion", "--help"}


def _walk(command: Any, path: str) -> list[tuple[str, Any]]:
    found = [(path, command)]
    for name, sub in getattr(command, "commands", {}).items():
        found += _walk(sub, f"{path} {name}")
    return found


def _default(param: Any) -> str:
    default = getattr(param, "default", None)
    if getattr(param, "is_flag", False) or default in (None, (), [], ""):
        return ""
    return f"`{default}`"


def _kind(param: Any) -> str:
    if getattr(param, "is_flag", False):
        return "flag"
    name = getattr(getattr(param, "type", None), "name", "") or ""
    return {"text": "text", "integer": "int", "float": "number", "path": "path"}.get(
        name, name or "text"
    )


def _table(rows: list[tuple[str, str, str, str]]) -> list[str]:
    lines = ["| Option | Type | Default | What it does |", "|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    return lines


def _section(path: str, command: Any) -> list[str]:
    depth = 2 if path.count(" ") == 1 else 3
    lines = [f"{'#' * depth} `{path}`", ""]
    lines += [inspect.cleandoc(command.help or ""), ""]
    arguments = [
        p for p in command.params if not getattr(p, "opts", [""])[0].startswith("-") and p.name
    ]
    options = [
        p
        for p in command.params
        if getattr(p, "opts", None) and p.opts[0].startswith("-") and not set(p.opts) & SKIP
    ]
    if arguments:
        lines += ["Arguments:", ""]
        for p in arguments:
            lines.append(f"- `{p.name.upper()}`: {p.help or ''}".rstrip())
        lines.append("")
    if options:
        rows = []
        for p in options:
            names = ", ".join(f"`{o}`" for o in p.opts)
            required = " (required)" if getattr(p, "required", False) else ""
            rows.append((names, _kind(p), _default(p), f"{p.help or ''}{required}".strip()))
        lines += [*_table(rows), ""]
    epilog = getattr(command, "epilog", None)
    if epilog:
        body = [x for x in inspect.cleandoc(epilog.replace("\b\n", "")).splitlines()]
        examples = [x.strip() for x in body if x.strip().startswith("saidby ")]
        if examples:
            lines += ["Examples:", "", "```bash", *examples, "```", ""]
    return lines


def render() -> str:
    root = typer.main.get_command(app)
    lines = [
        "# Command reference",
        "",
        "Generated from `saidby --help` by `tools/gen_cli_reference.py`; do not edit by hand. "
        "For a guided tour of the commands see [commands.md](commands.md).",
        "",
    ]
    for path, command in _walk(root, "saidby")[1:]:
        if getattr(command, "commands", None):
            lines += [f"## `{path}`", "", inspect.cleandoc(command.help or ""), ""]
            continue
        lines += _section(path, command)
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
