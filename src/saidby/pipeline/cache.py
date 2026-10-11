# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
from pathlib import Path
from typing import Any

from saidby.schema.engine import EngineInfo

ARTIFACT_SCHEMA = {
    "ingest": 1,
    "asr": 1,
    "diarize": 1,
    "align": 1,
    "tracks": 1,
}


def stage_key(
    stage: str,
    *,
    inputs: dict[str, str],
    engine: EngineInfo | None = None,
    options: dict[str, Any] | None = None,
) -> str:
    engine_part = (
        {k: getattr(engine, k) for k in ("name", "model", "repo_id", "revision", "compute_type")}
        if engine
        else None
    )
    payload = {
        "stage": stage,
        "artifact_schema": ARTIFACT_SCHEMA.get(stage, 1),
        "inputs": inputs,
        "engine": engine_part,
        "options": options or {},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def marker_path(work_dir: Path, stage: str) -> Path:
    return work_dir / f"stage.{stage}.json"


def read_marker(work_dir: Path, stage: str) -> dict[str, Any] | None:
    path = marker_path(work_dir, stage)
    if not path.is_file():
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data


def write_marker(work_dir: Path, stage: str, key: str, **extra: Any) -> None:
    marker_path(work_dir, stage).write_text(
        json.dumps({"key": key, **extra}, sort_keys=True), encoding="utf-8"
    )


def is_fresh(work_dir: Path, stage: str, key: str, artifacts: list[Path]) -> bool:
    marker = read_marker(work_dir, stage)
    return bool(marker and marker.get("key") == key and all(a.exists() for a in artifacts))
