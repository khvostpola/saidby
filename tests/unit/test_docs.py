# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import re
import shlex
import sys
from pathlib import Path
from typing import Any

import pytest
import typer.main

from saidby.cli import app

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import diagrams  # noqa: E402
import gen_cli_reference  # noqa: E402

DOCS = sorted([ROOT / "README.md", ROOT / "CONTRIBUTING.md", *(ROOT / "docs").glob("*.md")])
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
FENCE = re.compile(r"```([a-z]*)\n(.*?)```", re.S)
BASE = "https://github.com/khvostpola/saidby/blob/main/"
RAW = "https://raw.githubusercontent.com/khvostpola/saidby/main/"


def _slug(heading: str) -> str:
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def _anchors(path: Path) -> set[str]:
    return {_slug(m) for m in re.findall(r"^#{1,6}\s+(.*)$", path.read_text(), re.M)}


def _local(target: str, source: Path) -> tuple[Path, str] | None:
    for prefix in (BASE, RAW):
        if target.startswith(prefix):
            target, source = target[len(prefix) :], ROOT / "README.md"
            break
    if re.match(r"[a-z]+://", target):
        return None
    file_part, _, anchor = target.partition("#")
    path = source if not file_part else (source.parent / file_part).resolve()
    return path, anchor


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_links_images_and_anchors_resolve(doc: Path) -> None:
    text = doc.read_text()
    broken = []
    for target in [*LINK.findall(text), *IMAGE.findall(text)]:
        resolved = _local(target, doc)
        if resolved is None:
            continue
        path, anchor = resolved
        if not path.exists() or (anchor and path.suffix == ".md" and anchor not in _anchors(path)):
            broken.append(target)
    assert broken == []


def _commands() -> dict[str, Any]:
    root = typer.main.get_command(app)
    found: dict[str, Any] = {}

    def walk(command: Any, path: tuple[str, ...]) -> None:
        found[" ".join(path)] = command
        for name, sub in getattr(command, "commands", {}).items():
            walk(sub, (*path, name))

    walk(root, ())
    return found


def _doc_commands() -> list[tuple[str, str]]:
    found = []
    for doc in DOCS:
        for language, block in FENCE.findall(doc.read_text()):
            if language not in {"bash", "sh", ""}:
                continue
            joined = re.sub(r"\\\n\s*", " ", block)
            for line in joined.splitlines():
                if line.strip().startswith("saidby ") and not re.match(r"saidby \d", line.strip()):
                    found.append((doc.name, line.strip()))
    return found


@pytest.mark.parametrize(("doc", "line"), _doc_commands())
def test_every_documented_command_and_option_exists(doc: str, line: str) -> None:
    commands = _commands()
    cleaned = re.sub(r"\s+#.*$", "", line)
    tokens = shlex.split(cleaned.replace("[", "").replace("]", "").replace("|", " "))[1:]
    path: list[str] = []
    for token in tokens:
        candidate = " ".join([*path, token])
        if not token.startswith("-") and candidate in commands:
            path.append(token)
        else:
            break
    if not path:
        assert tokens[0] in {"--help", "-h", "--version"}, f"{doc}: {line}"
        return
    command = commands[" ".join(path)]
    known = {o for p in getattr(command, "params", []) for o in getattr(p, "opts", [])}
    known |= {"--help", "-h"}
    used = {t.split("=")[0] for t in tokens if t.startswith("-")}
    assert used <= known, f"{doc}: {line}: unknown option(s) {sorted(used - known)}"


def test_diagrams_are_up_to_date(tmp_path: Path) -> None:
    for name, build in diagrams.DIAGRAMS.items():
        assert (ROOT / "docs/img" / f"{name}.svg").read_text() == build(), (
            f"docs/img/{name}.svg is stale: run `uv run python tools/diagrams.py`"
        )


def test_cli_reference_is_up_to_date() -> None:
    assert (ROOT / "docs/cli-reference.md").read_text() == gen_cli_reference.render(), (
        "docs/cli-reference.md is stale: run `uv run python tools/gen_cli_reference.py`"
    )


def test_every_svg_is_referenced_by_the_docs() -> None:
    text = "\n".join(p.read_text() for p in DOCS)
    for svg in (ROOT / "docs/img").glob("*.svg"):
        assert svg.name in text, f"{svg.name} is not used anywhere"
