# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from saidby.schema.correction import Correction


def write_corrections(path: Path, corrections: list[Correction]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(c.model_dump_json(by_alias=True, exclude_none=True) + "\n" for c in corrections),
        encoding="utf-8",
        newline="\n",
    )


def read_corrections(path: Path) -> list[Correction]:
    if not path.is_file():
        return []
    return [
        Correction.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
