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


def show_path(path: Path) -> str:
    try:
        return "." + os.sep + str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        pass
    try:
        return "~" + os.sep + str(path.resolve().relative_to(Path.home()))
    except ValueError:
        return str(path)
