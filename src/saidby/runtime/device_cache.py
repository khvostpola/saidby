# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from saidby import __version__
from saidby.runtime import host
from saidby.runtime.device import DeviceInfo

CACHE_SCHEMA = "saidby.device/1"


@dataclass(frozen=True)
class CachedDevice:
    kind: str
    name: str | None
    vram_total_mb: int | None
    reason: str | None
    checked_at: datetime


def cache_path() -> Path:
    return host.cache_dir() / "device.json"


def write_cache(device: DeviceInfo, now: datetime | None = None) -> None:
    record = {
        "schema": CACHE_SCHEMA,
        "saidby": __version__,
        "checked_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "kind": device.kind,
        "name": device.name,
        "vram_total_mb": device.vram_total_mb,
        "reason": device.reason,
    }
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(record), encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    except OSError:
        return


def read_cache() -> CachedDevice | None:
    try:
        data = json.loads(cache_path().read_text(encoding="utf-8"))
        if data["schema"] != CACHE_SCHEMA or data["saidby"] != __version__:
            return None
        return CachedDevice(
            kind=str(data["kind"]),
            name=data.get("name"),
            vram_total_mb=data.get("vram_total_mb"),
            reason=data.get("reason"),
            checked_at=datetime.fromisoformat(data["checked_at"]),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None
