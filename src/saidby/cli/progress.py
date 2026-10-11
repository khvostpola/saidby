# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import sys
from typing import Any


def fmt_clock(seconds: float) -> str:
    minutes, secs = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class Progress:
    def __init__(self, mode: str = "human") -> None:
        self.mode = mode

    def stage_end(
        self,
        *,
        index: int,
        total: int,
        slug: str,
        stage: str,
        parts: list[str],
        wall_s: float,
        rtf: float | None,
        cached: bool,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if self.mode == "json":
            event = {
                "event": "stage.skip" if cached else "stage.end",
                "file": slug,
                "stage": stage,
                "wall_s": wall_s,
                "rtf": rtf,
                **(extra or {}),
            }
            print(json.dumps(event), flush=True)
        elif self.mode == "human":
            tail = "cached" if cached else f"{fmt_clock(wall_s)}" + (f"  {rtf:.3f}x" if rtf else "")
            print(
                f"[{index}/{total}] {stage:<10} {' · '.join(parts)}   {tail}",
                file=sys.stderr,
                flush=True,
            )

    def file_end(
        self, *, index: int, total: int, slug: str, status: str, out: str, detail: str
    ) -> None:
        if self.mode == "json":
            print(
                json.dumps({"event": "file.end", "file": slug, "status": status, "out": out}),
                flush=True,
            )
        elif self.mode == "human":
            print(f"[{index}/{total}] {status:<10} {out} · {detail}", file=sys.stderr, flush=True)

    def stage_error(
        self, *, index: int, total: int, slug: str, stage: str, error_type: str
    ) -> None:
        if self.mode == "json":
            print(
                json.dumps(
                    {"event": "stage.error", "file": slug, "stage": stage, "error_type": error_type}
                ),
                flush=True,
            )
        elif self.mode == "human":
            print(
                f"[{index}/{total}] {stage:<10} failed: {error_type}", file=sys.stderr, flush=True
            )
