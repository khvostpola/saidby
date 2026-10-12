# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import sys
import threading
import time
from datetime import datetime
from typing import Any, TextIO

ACTIVITY = {
    "ingest": "converting the audio",
    "asr": "transcribing",
    "asr_bias": "second pass with your terms",
    "transplant": "merging your terms",
    "diarize": "finding the speakers",
    "compare": "running the second diarizer",
    "identify": "matching voices",
    "correct": "asking the local model",
    "align": "giving each word a speaker",
    "tracks": "writing the tracks",
    "outputs": "writing the files",
}
CLEAR = "\r\x1b[K"


def fmt_clock(seconds: float) -> str:
    minutes, secs = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def fmt_moment(moment: datetime, relative_to: datetime | None = None) -> str:
    text = moment.strftime("%I:%M:%S %p").lstrip("0")
    if relative_to is not None and moment.date() != relative_to.date():
        return f"{moment.strftime('%b')} {moment.day}, {text}"
    return text


class Progress:
    def __init__(
        self,
        mode: str = "human",
        stream: TextIO | None = None,
        delay_s: float = 0.4,
        interval_s: float = 0.5,
    ) -> None:
        self.mode = mode
        self.stream: TextIO = stream or sys.stderr
        self.delay_s = delay_s
        self.interval_s = interval_s
        self.live = (
            mode == "human"
            and self.stream.isatty()
            and os.environ.get("TERM", "") not in {"", "dumb"}
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._drew = False

    def stage_start(self, *, index: int, total: int, slug: str, stage: str) -> None:
        self.stop()
        if self.mode == "json":
            print(json.dumps({"event": "stage.start", "file": slug, "stage": stage}), flush=True)
        elif self.live:
            self._stop = threading.Event()
            self._drew = False
            self._thread = threading.Thread(
                target=self._tick, args=(index, total, stage, time.monotonic()), daemon=True
            )
            self._thread.start()

    def _tick(self, index: int, total: int, stage: str, started: float) -> None:
        if self._stop.wait(self.delay_s):
            return
        activity = ACTIVITY.get(stage, "working")
        while True:
            elapsed = fmt_clock(time.monotonic() - started)
            self.stream.write(f"{CLEAR}[{index}/{total}] {stage:<10} {activity}...  {elapsed}")
            self.stream.flush()
            self._drew = True
            if self._stop.wait(self.interval_s):
                return

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=2)
        if self._drew:
            self.stream.write(CLEAR)
            self.stream.flush()
        self._thread = None

    def _line(self, text: str) -> None:
        print(text, file=self.stream, flush=True)

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
        self.stop()
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
            self._line(f"[{index}/{total}] {stage:<10} {' · '.join(parts)}   {tail}")

    def file_end(
        self, *, index: int, total: int, slug: str, status: str, out: str, detail: str
    ) -> None:
        self.stop()
        if self.mode == "json":
            print(
                json.dumps({"event": "file.end", "file": slug, "status": status, "out": out}),
                flush=True,
            )
        elif self.mode == "human":
            self._line(f"[{index}/{total}] {status:<10} {out} · {detail}")

    def stage_error(
        self, *, index: int, total: int, slug: str, stage: str, error_type: str
    ) -> None:
        self.stop()
        if self.mode == "json":
            print(
                json.dumps(
                    {"event": "stage.error", "file": slug, "stage": stage, "error_type": error_type}
                ),
                flush=True,
            )
        elif self.mode == "human":
            self._line(f"[{index}/{total}] {stage:<10} failed: {error_type}")

    def summary(
        self,
        *,
        started: datetime,
        finished: datetime,
        wall_s: float,
        audio_s: float,
        files: int,
        failed: int,
    ) -> None:
        self.stop()
        rtf = wall_s / audio_s if audio_s > 0 else None
        if self.mode == "json":
            print(
                json.dumps(
                    {
                        "event": "run.end",
                        "started": started.isoformat(timespec="seconds"),
                        "finished": finished.isoformat(timespec="seconds"),
                        "wall_s": round(wall_s, 1),
                        "audio_s": round(audio_s, 1),
                        "rtf": round(rtf, 3) if rtf else None,
                        "files": files,
                        "failed": failed,
                    }
                ),
                flush=True,
            )
        elif self.mode == "human":
            parts = [
                f"started {fmt_moment(started)}",
                f"finished {fmt_moment(finished, started)}",
                f"{fmt_clock(audio_s)} of audio" + (f" at {rtf:.2f}x" if rtf else ""),
            ]
            if files > 1:
                parts.append(f"{files} files")
            if failed:
                parts.append(f"{failed} failed")
            self._line(f"[total]    {fmt_clock(wall_s)}   {' · '.join(parts)}")
