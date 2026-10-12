# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os

from saidby.cli.term import Terminal
from saidby.i18n import _, ngettext
from saidby.runtime.device import DeviceInfo
from saidby.runtime.usage import CpuUsage, GpuUsage, Usage

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
        problem = _(device.note.removeprefix("running on CPU: "))
        hint = _("{problem} (details: saidby doctor)").format(problem=problem)
        lines.append(f"{' ' * (LABEL_WIDTH + 1)}{term.paint(hint, 'dim')}")
    return lines


def activity_text(stage: str) -> str:
    texts = {
        "ingest": _("converting the audio"),
        "asr": _("transcribing"),
        "asr_bias": _("second pass with your terms"),
        "transplant": _("merging your terms"),
        "diarize": _("finding the speakers"),
        "compare": _("running the second diarizer"),
        "identify": _("matching voices"),
        "correct": _("asking the local model"),
        "align": _("giving each word a speaker"),
        "tracks": _("writing the tracks"),
        "outputs": _("writing the files"),
    }
    return texts.get(stage, _("working"))


def loading_text(model: str, device: DeviceInfo | None) -> str:
    if device is not None and device.kind == "cuda":
        return _("loading {model} into the GPU").format(model=model)
    return _("loading {model}").format(model=model)


def format_usage(usage: Usage) -> str:
    if isinstance(usage, GpuUsage):
        used, total = usage.used_mb / 1024, usage.total_mb / 1024
        return f"GPU {used:.1f}/{total:.1f} GB · {usage.util_pct}%"
    assert isinstance(usage, CpuUsage)
    return _("CPU {threads} threads · {pct}%").format(threads=usage.threads, pct=usage.util_pct)


FOLDED = frozenset({"transplant", "align", "tracks", "outputs"})


def stage_label(stage: str) -> str:
    labels = {
        "ingest": _("audio"),
        "asr": _("transcript"),
        "asr_bias": _("terms"),
        "diarize": _("speakers"),
        "compare": _("compare"),
        "identify": _("names"),
        "correct": _("correct"),
    }
    return labels.get(stage, stage)


def label_width() -> int:
    stages = ("ingest", "asr", "asr_bias", "diarize", "compare", "identify", "correct")
    return max(10, *(len(stage_label(s)) for s in stages))


def status_label(status: str) -> str:
    labels = {
        "done": _("done"),
        "failed": _("failed"),
        "interrupted": _("interrupted"),
    }
    return labels.get(status, status)


def _compact(value: float) -> str:
    text = f"{value:.0f}" if value >= 10 else f"{value:.1f}"
    return text.removesuffix(".0")


def speed_text(rtf: float) -> str:
    if rtf <= 1:
        return _("{factor}x faster than the audio").format(factor=_compact(1 / rtf))
    return _("{factor}x slower than the audio").format(factor=_compact(rtf))


def done_detail(speakers: int, tracks: int, terms_fixed: int) -> str:
    parts = [ngettext("{n} speaker", "{n} speakers", speakers).format(n=speakers)]
    if tracks:
        parts.append(ngettext("{n} track", "{n} tracks", tracks).format(n=tracks))
    if terms_fixed:
        parts.append(
            ngettext("{n} term fixed", "{n} terms fixed", terms_fixed).format(n=terms_fixed)
        )
    return " · ".join(parts)
