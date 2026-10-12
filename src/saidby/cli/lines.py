# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os

from saidby.cli.term import Terminal
from saidby.i18n import _
from saidby.runtime.device import DeviceInfo

LABEL_WIDTH = 11


def _gb(megabytes: int | None) -> str:
    return f"{round(megabytes / 1024)} GB" if megabytes else ""


def _cpu_value() -> str:
    return _("CPU · {threads} threads").format(threads=os.cpu_count() or 1)


def _fallback_reason(device: DeviceInfo) -> str:
    if device.reason == "gpu_unusable":
        return _("the GPU cannot be used")
    return _("no NVIDIA GPU found")


def format_device(device: DeviceInfo, requested: str, term: Terminal) -> list[str]:
    label = term.paint(f"{_('device'):<{LABEL_WIDTH}}", "bold")
    if device.kind == "cuda":
        parts = ["GPU", "cuda", *(p for p in (device.name, _gb(device.vram_total_mb)) if p)]
        value = term.paint(" · ".join(parts), "green")
        how = f"({requested} → cuda)" if requested == "auto" else "(--device cuda)"
        return [f"{label} {value}   {term.paint(how, 'dim')}"]
    if device.reason == "requested_cpu":
        how = term.paint("(--device cpu)", "dim")
        return [f"{label} {_cpu_value()}   {how}"]
    how = f"({requested} → cpu: {_fallback_reason(device)})"
    lines = [f"{label} {term.paint(_cpu_value(), 'yellow')}   {term.paint(how, 'yellow')}"]
    if device.reason == "gpu_unusable" and device.note:
        problem = device.note.removeprefix("running on CPU: ")
        hint = _("{problem} (details: saidby doctor)").format(problem=problem)
        lines.append(f"{' ' * (LABEL_WIDTH + 1)}{term.paint(hint, 'dim')}")
    return lines
