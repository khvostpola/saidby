# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


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
    return path.with_name(f"{path.stem}.bak-{stamp}{path.suffix}")


def save_yaml(path: Path, data: Any, *, backup: bool = True) -> Path | None:
    saved: Path | None = None
    if backup and path.exists():
        saved = backup_path(path)
        shutil.copy2(path, saved)
    offset = sequence_offset(path, data)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        _yaml(offset).dump(data, fh)
    os.replace(tmp, path)
    return saved
