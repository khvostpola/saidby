# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any, TextIO

from saidby import __version__
from saidby.cli.lines import (
    FOLDED,
    LABEL_WIDTH,
    activity_text,
    format_device,
    format_usage,
    label_width,
    loading_text,
    speed_text,
    stage_label,
    status_label,
)
from saidby.cli.term import Terminal, detect
from saidby.i18n import _, ngettext
from saidby.runtime.device import DeviceInfo
from saidby.runtime.usage import Probe

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
        terminal: Terminal | None = None,
    ) -> None:
        self.mode = mode
        self.stream: TextIO = stream or sys.stderr
        self.delay_s = delay_s
        self.interval_s = interval_s
        self.terminal = terminal or detect(self.stream)
        self.live = mode == "human" and self.terminal.tty
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._drew = False
        self._prefix = ""
        self._activity = ""
        self._stage = ""
        self._slug = ""
        self._device: DeviceInfo | None = None
        self._probe: Probe | None = None
        self._with_usage = False

    def stage_start(self, *, index: int, total: int, slug: str, stage: str) -> None:
        self.stop()
        self._stage, self._slug = stage, slug
        if self.mode == "json":
            print(json.dumps({"event": "stage.start", "file": slug, "stage": stage}), flush=True)
        else:
            prefix = f"[{index}/{total}] {stage_label(stage):<{label_width()}} "
            self._start_live(prefix, activity_text(stage), with_usage=True)

    def _start_live(self, prefix: str, activity: str, *, with_usage: bool = False) -> None:
        self._prefix, self._activity, self._with_usage = prefix, activity, with_usage
        if not self.live:
            return
        self._stop = threading.Event()
        self._drew = False
        self._thread = threading.Thread(target=self._tick, args=(time.monotonic(),), daemon=True)
        self._thread.start()

    def _usage_text(self) -> str | None:
        if not (self._with_usage and self._probe):
            return None
        try:
            usage = self._probe()
        except Exception:
            return None
        return format_usage(usage) if usage else None

    def _compose(self, line: str, usage: str | None) -> str:
        suffix = f"  ·  {usage}" if usage else ""
        if not usage or len(line) + len(suffix) > self.terminal.columns - 1:
            return self.terminal.fit(line)
        return line + self.terminal.paint(suffix, "dim")

    def _tick(self, started: float) -> None:
        if self._stop.wait(self.delay_s):
            return
        while True:
            elapsed = fmt_clock(time.monotonic() - started)
            line = f"{self._prefix}{self._activity}...  {elapsed}"
            self.stream.write(CLEAR + self._compose(line, self._usage_text()))
            self.stream.flush()
            self._drew = True
            if self._stop.wait(self.interval_s):
                return

    def track_usage(self, device: DeviceInfo, probe: Probe | None) -> None:
        self._device, self._probe = device, probe

    def loading(self, model: str) -> None:
        if self.mode == "json":
            event = {"event": "stage.loading", "file": self._slug, "stage": self._stage}
            print(json.dumps({**event, "model": model}), flush=True)
        elif self.mode == "human":
            self._activity = loading_text(model, self._device)

    def running(self) -> None:
        self._activity = activity_text(self._stage)

    @contextmanager
    def phase(self, label: str, activity: str) -> Iterator[None]:
        self.stop()
        self._start_live(f"{label:<{LABEL_WIDTH}} ", activity)
        try:
            yield
        finally:
            self.stop()

    def run_start(self) -> None:
        if self.mode == "json":
            print(json.dumps({"event": "run.start", "saidby": __version__}), flush=True)

    def device(self, device: DeviceInfo, requested: str) -> None:
        self.stop()
        if self.mode == "json":
            event = {
                "event": "device",
                "requested": requested,
                "used": device.kind,
                "name": device.name,
                "vram_total_mb": device.vram_total_mb,
                "reason": device.reason,
            }
            print(json.dumps(event), flush=True)
        elif self.mode == "human":
            for line in format_device(device, requested, self.terminal):
                self._line(line)

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
        elif self.mode == "human" and stage not in FOLDED:
            tail = _("cached") if cached else fmt_clock(wall_s)
            if rtf and not cached:
                tail += f" · {speed_text(rtf)}"
            label = f"{stage_label(stage):<{label_width()}}"
            self._line(f"[{index}/{total}] {label} {' · '.join(parts)}   {tail}")

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
            self._line(
                f"[{index}/{total}] {status_label(status):<{label_width()}} {out} · {detail}"
            )

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
            label = f"{stage_label(stage):<{label_width()}}"
            self._line(f"[{index}/{total}] {label} {_('failed')}: {error_type}")

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
                _("started {moment}").format(moment=fmt_moment(started)),
                _("finished {moment}").format(moment=fmt_moment(finished, started)),
                _("{duration} of audio").format(duration=fmt_clock(audio_s))
                + (f" · {speed_text(rtf)}" if rtf else ""),
            ]
            if files > 1:
                parts.append(ngettext("{n} file", "{n} files", files).format(n=files))
            if failed:
                parts.append(_("{n} failed").format(n=failed))
            self._line(f"[total]    {fmt_clock(wall_s)}   {' · '.join(parts)}")
