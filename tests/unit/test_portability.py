# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

"""Keeps the tree portable: UTF-8 text, LF line endings, no POSIX-only shortcuts.

Windows reads and writes text in the ANSI code page unless told otherwise, so every text file
call names its encoding, and every writer fixes its line endings so outputs are byte-identical
on every system.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TREES = {"src": ROOT / "src", "tools": ROOT / "tools", "tests": ROOT / "tests"}
NEWLINE_TREES = ("src", "tools")
WRITE_MODES = set("wax+")
BINARY_RECEIVERS = {"tarfile", "zipfile", "gzip", "bz2", "lzma", "io", "urllib", "webbrowser", "os"}
TEXT_RULES: dict[str, tuple[str, set[str]]] = {
    "shlex": ("quote through saidby.runtime.host", {"src/saidby/runtime/host.py"}),
    "~/.config": (
        "the config folder comes from saidby.runtime.host",
        {"src/saidby/runtime/host.py", "src/saidby/cli/init.py", "src/saidby/cli/directory.py"},
    ),
}


def _python_files(tree: str) -> Iterator[Path]:
    yield from sorted(TREES[tree].rglob("*.py"))


def _where(path: Path, node: ast.AST) -> str:
    return f"{path.relative_to(ROOT).as_posix()}:{getattr(node, 'lineno', 0)}"


def _mode(call: ast.Call, position: int) -> str | None:
    if len(call.args) > position:
        arg = call.args[position]
        return arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None
    for kw in call.keywords:
        if kw.arg == "mode":
            v = kw.value
            return v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else None
    return "r"


def _text_call(call: ast.Call) -> tuple[str, bool] | None:
    """(kind, writes) for a call that opens a text file, else None."""
    func = call.func
    if isinstance(func, ast.Name) and func.id == "open":
        kind = "open"
    elif isinstance(func, ast.Attribute) and func.attr in ("open", "read_text", "write_text"):
        if isinstance(func.value, ast.Name) and func.value.id in BINARY_RECEIVERS:
            return None
        kind = func.attr
    else:
        return None
    if any(kw.arg is None for kw in call.keywords):
        return None
    if kind != "open":
        return kind, kind == "write_text"
    mode = _mode(call, 1 if isinstance(func, ast.Name) else 0)
    if mode is None or "b" in mode:
        return None
    return kind, bool(set(mode) & WRITE_MODES)


def _calls(tree: str) -> Iterator[tuple[Path, ast.Call]]:
    for path in _python_files(tree):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if isinstance(node, ast.Call):
                yield path, node


def _keywords(call: ast.Call) -> set[str | None]:
    return {kw.arg for kw in call.keywords}


def test_every_text_file_call_names_its_encoding() -> None:
    problems = [
        f"{_where(path, call)}: {kind}() without encoding="
        for tree in TREES
        for path, call in _calls(tree)
        if (found := _text_call(call)) and "encoding" not in _keywords(call)
        for kind, _writes in [found]
    ]
    assert problems == []


def test_every_text_writer_fixes_its_line_endings() -> None:
    problems = [
        f"{_where(path, call)}: {kind}() without newline="
        for tree in NEWLINE_TREES
        for path, call in _calls(tree)
        if (found := _text_call(call)) and found[1] and "newline" not in _keywords(call)
        for kind, _writes in [found]
    ]
    assert problems == []


def test_source_keeps_system_specifics_inside_host() -> None:
    problems = []
    for path in _python_files("src"):
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for needle, (why, allowed) in TEXT_RULES.items():
            if needle in text and relative not in allowed:
                problems.append(f"{relative}: {needle!r} ({why})")
    assert problems == []
