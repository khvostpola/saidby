# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 1_000_000
    yaml.indent(mapping=2, sequence=2, offset=0)
    return yaml


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
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        _yaml().dump(data, fh)
    os.replace(tmp, path)
    return saved
