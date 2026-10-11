# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import base64
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import ValidationError

from saidby.errors import InputError
from saidby.formats.yaml_io import load_yaml, save_yaml
from saidby.schema.directory import Directory


def plain(data: Any) -> Any:
    if isinstance(data, dict):
        return {str(k): plain(v) for k, v in data.items()}
    if isinstance(data, list):
        return [plain(v) for v in data]
    return data


def validate_directory(raw: Any) -> Directory:
    try:
        return Directory.model_validate(plain(raw))
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise InputError(f"invalid directory at {where}: {first['msg']}") from exc


def load_directory(path: Path) -> tuple[Directory, Any]:
    if not path.is_file():
        raise InputError(f"directory file not found: {path}")
    raw = load_yaml(path)
    return validate_directory(raw), raw


def save_directory(path: Path, raw: Any) -> Path | None:
    validate_directory(raw)
    return save_yaml(path, raw)


def encode_vector(vector: np.ndarray) -> str:
    return base64.b64encode(vector.astype(np.float32).tobytes()).decode()


def decode_vector(text: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(text), dtype=np.float32)
