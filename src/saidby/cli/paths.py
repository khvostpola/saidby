# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path

QUOTES = "\"'"


def unquote(text: str) -> str:
    """Drop the quotes that "Copy as path" and drag-and-drop put around a path."""
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in QUOTES:
        return text[1:-1]
    return text


def typed_path(text: str) -> Path:
    return Path(unquote(text)).expanduser()


def join_split_names(args: list[Path]) -> list[tuple[Path, int]]:
    """Each input with the number of arguments it took.

    A name with spaces typed without quotes arrives split into several arguments. An argument
    that is not a file is joined, with single spaces, to the ones after it as soon as the
    joined name is a file; otherwise it stays on its own.
    """
    found: list[tuple[Path, int]] = []
    start = 0
    while start < len(args):
        size = 1 if args[start].is_file() else _split_size(args, start)
        found.append((_joined(args[start : start + size]), size))
        start += size
    return found


def _joined(parts: list[Path]) -> Path:
    return parts[0] if len(parts) == 1 else Path(" ".join(str(part) for part in parts))


def _split_size(args: list[Path], start: int) -> int:
    for end in range(start + 2, len(args) + 1):
        if _joined(args[start:end]).is_file():
            return end - start
    return 1


def show_path(path: Path) -> str:
    try:
        return "." + os.sep + str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        pass
    try:
        return "~" + os.sep + str(path.resolve().relative_to(Path.home()))
    except ValueError:
        return str(path)
