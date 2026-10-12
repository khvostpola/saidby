# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TextIO

from saidby import __version__
from saidby.cli.banner_art import (
    CASSETTE,
    CASSETTE_MINI,
    FONT,
    LETTER_COLOR,
    PALETTE,
    SHADOW_COLOR,
    WORDMARK,
)
from saidby.cli.paths import show_path
from saidby.cli.term import RESET, Terminal, detect
from saidby.errors import SaidbyError
from saidby.i18n import _, ngettext

Rgb = tuple[int, int, int]
Cell = tuple[Rgb | None, Rgb | None]
Mark = Literal["ok", "warn", "alert", "off"]

FULL_WIDTH = 78
FULL_MIN_COLUMNS = 80
COMPACT_MIN_COLUMNS = 60
WORD_WIDTH = 34
LABEL_WIDTH = 13


def _grid(rows: list[str]) -> list[list[Rgb | None]]:
    return [[None if ch == "." else PALETTE[ch] for ch in row] for row in rows]


def _pairs(grid: list[list[Rgb | None]]) -> list[list[Cell]]:
    out: list[list[Cell]] = []
    for y in range(0, len(grid), 2):
        below = grid[y + 1] if y + 1 < len(grid) else [None] * len(grid[y])
        out.append(list(zip(grid[y], below, strict=True)))
    return out


def _word_grid() -> list[list[Rgb | None]]:
    grid: list[list[Rgb | None]] = [[None] * WORD_WIDTH for _ in range(8)]
    glyphs = [FONT[c] for c in WORDMARK]
    for color, dx, dy in ((SHADOW_COLOR, 1, 1), (LETTER_COLOR, 0, 0)):
        x = 0
        for glyph in glyphs:
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "#":
                        grid[gy + dy][x + gx + dx] = PALETTE[color]
            x += len(glyph[0]) + 1
    return grid


CASSETTE_ROWS = _pairs(_grid(CASSETTE))
MINI_ROWS = _pairs(_grid(CASSETTE_MINI))
WORD_ROWS = _pairs(_word_grid())


def _fg(color: Rgb) -> str:
    return f"\x1b[38;2;{color[0]};{color[1]};{color[2]}m"


def _bg(color: Rgb) -> str:
    return f"\x1b[48;2;{color[0]};{color[1]};{color[2]}m"


def render_cells(cells: list[Cell]) -> str:
    out: list[str] = []
    fg: Rgb | None = None
    bg: Rgb | None = None
    for top, bottom in cells:
        if top is None and bottom is None:
            if fg is not None or bg is not None:
                out.append(RESET)
                fg = bg = None
            out.append(" ")
            continue
        if top == bottom:
            glyph, want_fg, want_bg = "█", top, None
        elif bottom is None:
            glyph, want_fg, want_bg = "▀", top, None
        elif top is None:
            glyph, want_fg, want_bg = "▄", bottom, None
        else:
            glyph, want_fg, want_bg = "▀", top, bottom
        if want_bg is None and bg is not None:
            out.append("\x1b[49m")
            bg = None
        if want_bg is not None and want_bg != bg:
            out.append(_bg(want_bg))
            bg = want_bg
        if want_fg != fg and want_fg is not None:
            out.append(_fg(want_fg))
            fg = want_fg
        out.append(glyph)
    if fg is not None or bg is not None:
        out.append(RESET)
    return "".join(out)


@dataclass(frozen=True)
class InfoRow:
    mark: Mark
    label: str
    value: str
    detail: str | None = None


def _center(text: str, width: int) -> str:
    left = max(0, (width - len(text)) // 2)
    return (" " * left + text).ljust(width)


def _info_lines(rows: list[InfoRow], term: Terminal) -> list[str]:
    marks: dict[Mark, tuple[str, str]] = {
        "ok": ("●", "green"),
        "warn": ("●", "yellow"),
        "alert": ("▲", "yellow"),
        "off": ("○", "dim"),
    }
    lines: list[str] = []
    for row in rows:
        symbol, color = marks[row.mark]
        label = term.paint(row.label.ljust(LABEL_WIDTH), "bold")
        value = term.paint(row.value, color) if row.mark in {"warn", "alert"} else row.value
        lines.append(f"  {term.paint(symbol, color)} {label}{value}")
        if row.detail:
            lines.append(" " * (4 + LABEL_WIDTH) + term.paint(row.detail, "dim"))
    return lines


def full_lines(term: Terminal, rows: list[InfoRow], tip: str | None = None) -> list[str]:
    def corners(left: str, right: str) -> str:
        return term.paint(f" {left}{' ' * 74}{right} ", "dim")

    def with_cassette(left: str, row: int) -> str:
        return f"{left}{' ' * 13}{render_cells(CASSETTE_ROWS[row])}    "

    welcome = term.paint(f"   {_('Welcome to')}".ljust(37), "dim")
    tagline = term.paint(_center(_("Diarized transcription · offline"), WORD_WIDTH), "dim")
    lines = [corners("┌", "┐"), with_cassette(welcome, 0)]
    for k in range(4):
        lines.append(with_cassette(f"   {render_cells(WORD_ROWS[k])}", k + 1))
    lines.append(with_cassette(f"   {tagline}", 5))
    lines.append(with_cassette(" " * 37, 6))
    lines.append(with_cassette(" " * 37, 7))
    lines += [corners("└", "┘"), ""]
    lines += _info_lines(rows, term)
    lines.append("")
    if tip:
        lines.append(f"  {term.paint(_('Tip'), 'yellow')} {tip}")
    commands = [_("saidby process FILE"), "saidby doctor", "saidby --help"]
    joined = "   ".join(term.paint(c, "cyan") for c in commands)
    lines.append(f"  {joined}   {term.paint('v' + __version__, 'dim')}")
    return lines


def compact_lines(term: Terminal, second: str, third: str) -> list[str]:
    first = f"{term.paint('saidby', 'bold')} {term.paint(__version__, 'dim')}"
    texts = [first, second, term.paint(third, "dim")]
    return [f" {render_cells(MINI_ROWS[i])}  {texts[i]}" for i in range(3)]


def plain_line() -> str:
    return f"saidby {__version__} · {_('who said what, and when, on your own machine')}"


def ago(moment: datetime, now: datetime | None = None) -> str:
    seconds = max(0, int(((now or datetime.now(UTC)) - moment).total_seconds()))
    if seconds < 60:
        return _("just now")
    if seconds < 3600:
        return ngettext("{n} minute ago", "{n} minutes ago", seconds // 60).format(n=seconds // 60)
    if seconds < 48 * 3600:
        return _("{n} h ago").format(n=seconds // 3600)
    return _("{n} days ago").format(n=seconds // 86400)


def _models_row() -> InfoRow:
    from saidby.models import REGISTRY
    from saidby.models import store as model_store

    defaults = [s for s in REGISTRY if s.default]
    missing = [s for s in defaults if not model_store.is_installed(s)]
    if not missing:
        return InfoRow("ok", _("Models"), _("{n} default models ready").format(n=len(defaults)))
    value = _("{missing} of {total} default models missing").format(
        missing=len(missing), total=len(defaults)
    )
    return InfoRow("warn", _("Models"), value, "saidby models pull --all")


def _device_rows(now: datetime | None = None) -> list[InfoRow]:
    from saidby.runtime.device_cache import read_cache

    label = _("Device")
    cached = read_cache()
    if cached is None:
        return [
            InfoRow(
                "off",
                label,
                _("not checked yet"),
                _("confirmed on the first run or with saidby doctor"),
            )
        ]
    threads = os.cpu_count() or 1
    seen = _("confirmed on the last run, {when}").format(when=ago(cached.checked_at, now))
    if cached.kind == "cuda":
        memory = f" · {round(cached.vram_total_mb / 1024)} GB" if cached.vram_total_mb else ""
        name = f" · {cached.name}" if cached.name else ""
        return [InfoRow("ok", label, f"{_('GPU active')} · cuda{name}{memory}", seen)]
    if cached.reason == "gpu_unusable":
        value = f"{_('CPU active')} · {_('the NVIDIA GPU cannot be used')}"
        return [InfoRow("alert", label, value, _("details and the fix: saidby doctor"))]
    value = f"{_('CPU active')} · {threads} threads · {_('no NVIDIA GPU found')}"
    return [InfoRow("warn", label, value, _("slower than with a GPU"))]


def _glossary_and_config_rows() -> tuple[list[InfoRow], bool]:
    from saidby.config.settings import Settings
    from saidby.formats.directory_set import load_directory_set

    try:
        settings = Settings.load()
    except SaidbyError as exc:
        return [InfoRow("alert", _("Config"), str(exc))], False
    rows: list[InfoRow] = []
    if settings.directory:
        try:
            merged = load_directory_set(settings.directory).merged
            names = ", ".join(show_path(p) for p in settings.directory)
            people = ngettext("{n} person", "{n} people", len(merged.people))
            terms = ngettext("{n} term", "{n} terms", len(merged.terms))
            counts = f"{people.format(n=len(merged.people))} · {terms.format(n=len(merged.terms))}"
            rows.append(InfoRow("ok", _("Glossary"), f"{names} · {counts}"))
        except SaidbyError as exc:
            rows.append(InfoRow("alert", _("Glossary"), str(exc)))
    else:
        rows.append(InfoRow("off", _("Glossary"), _("none (see saidby init)")))
    if settings.sources:
        names = ", ".join(show_path(p) for p in settings.sources)
        language = settings.language or _("auto")
        output = show_path(settings.out) + os.sep
        rows.append(InfoRow("ok", _("Config"), f"{names} · {language} · {_('output')} {output}"))
        return rows, True
    rows.append(InfoRow("off", _("Config"), _("none found, using defaults")))
    return rows, False


def gather_rows() -> tuple[list[InfoRow], bool]:
    glossary, has_config = _glossary_and_config_rows()
    return [_models_row(), *_device_rows(), *glossary], has_config


def _emit(lines: list[str], stream: TextIO) -> None:
    for line in lines:
        print(line, file=stream)


def show_home(stream: TextIO | None = None, term: Terminal | None = None) -> None:
    out = stream or sys.stderr
    term = term or detect(out)
    if not term.tty:
        return
    try:
        if term.truecolor and term.columns >= FULL_MIN_COLUMNS:
            rows, has_config = gather_rows()
            tip = None if has_config else _("run saidby init to stop retyping options")
            _emit(full_lines(term, rows, tip), out)
        elif term.truecolor and term.columns >= COMPACT_MIN_COLUMNS:
            second = _("who said what, and when, on your own machine")
            _emit(compact_lines(term, second, _("saidby --help lists the commands")), out)
        else:
            print(plain_line(), file=out)
    except Exception:
        return


def show_compact(
    files: int, output: Path, stream: TextIO | None = None, term: Terminal | None = None
) -> None:
    out = stream or sys.stderr
    term = term or detect(out)
    if not (term.tty and term.truecolor and term.columns >= COMPACT_MIN_COLUMNS):
        return
    count = ngettext("{n} file", "{n} files", files).format(n=files)
    second = f"{count} · {_('output')} {show_path(output)}{os.sep}"
    third = _("Ctrl+C is safe: running again resumes where it stopped")
    try:
        _emit([*compact_lines(term, second, third), ""], out)
    except Exception:
        return
