# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from saidby import __version__
from saidby.schema.telemetry import TelemetryEvent


class TelemetrySink:
    def __init__(self, path: Path, run_id: str | None = None) -> None:
        self.path = path
        self.run_id = run_id or str(uuid.uuid4())
        path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **fields: Any) -> TelemetryEvent:
        record = TelemetryEvent.model_validate(
            {
                "event": event,
                "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "run_id": self.run_id,
                "tool_version": __version__,
                **fields,
            }
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(record.model_dump_json(exclude_none=True) + "\n")
        return record
