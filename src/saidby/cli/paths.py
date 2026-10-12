# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path


def show_path(path: Path) -> str:
    try:
        return "./" + str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        pass
    try:
        return "~/" + str(path.resolve().relative_to(Path.home()))
    except ValueError:
        return str(path)
