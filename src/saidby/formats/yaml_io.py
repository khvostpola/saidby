# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

REPLACE_ATTEMPTS = 3


def _yaml(offset: int = 0) -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 1_000_000
    yaml.indent(mapping=2, sequence=offset + 2, offset=offset)
    return yaml


def sequence_offset(path: Path, data: Any) -> int:
    default = 0 if isinstance(data, list) else 2
    try:
        match = re.search(r"^( *)- ", path.read_text(encoding="utf-8"), re.MULTILINE)
    except OSError:
        return default
    return len(match.group(1)) if match else default


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return _yaml().load(fh)


def backup_path(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.stem}.bak-{stamp}{path.suffix}")
    number = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}.bak-{stamp}-{number}{path.suffix}")
        number += 1
    return candidate


def save_yaml(path: Path, data: Any, *, backup: bool = True) -> Path | None:
    saved: Path | None = None
    if backup and path.exists():
        saved = backup_path(path)
        shutil.copy2(path, saved)
    offset = sequence_offset(path, data)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        _yaml(offset).dump(data, fh)
    _replace(tmp, path)
    return saved


def _replace(tmp: Path, path: Path) -> None:
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(0.1)
