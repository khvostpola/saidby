# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import contextlib
import io
import os
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TextIO

from saidby.runtime import host

RESET = "\x1b[0m"
CODES = {
    "bold": "1",
    "dim": "2",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "cyan": "36",
}
TRUECOLOR_VALUES = {"truecolor", "24bit"}
VT_PROCESSING = 0x0004


@dataclass(frozen=True)
class Terminal:
    tty: bool
    color: bool
    truecolor: bool
    columns: int

    def paint(self, text: str, *styles: str) -> str:
        if not self.color or not styles or not text:
            return text
        return f"\x1b[{';'.join(CODES[s] for s in styles)}m{text}{RESET}"

    def fit(self, text: str) -> str:
        limit = max(self.columns - 1, 10)
        return text if len(text) <= limit else text[: limit - 1] + "…"


def detect(
    stream: TextIO,
    environ: Mapping[str, str] | None = None,
    *,
    vt: Callable[[TextIO], bool] | None = None,
) -> Terminal:
    env = os.environ if environ is None else environ
    if host.is_windows():
        return _detect_windows(stream, env, vt or enable_vt)
    tty = stream.isatty() and env.get("TERM", "") not in {"", "dumb"}
    color = tty and not env.get("NO_COLOR")
    columns = shutil.get_terminal_size(fallback=(80, 24)).columns if tty else 80
    return Terminal(
        tty=tty,
        color=color,
        truecolor=color and env.get("COLORTERM", "").lower() in TRUECOLOR_VALUES,
        columns=columns,
    )


def _detect_windows(
    stream: TextIO, env: Mapping[str, str], vt: Callable[[TextIO], bool]
) -> Terminal:
    """Windows consoles set no TERM; a console is a terminal once it accepts ANSI escapes."""
    tty = stream.isatty() and env.get("TERM", "") != "dumb"
    color = tty and not env.get("NO_COLOR") and vt(stream)
    columns = shutil.get_terminal_size(fallback=(80, 24)).columns if tty else 80
    return Terminal(tty=tty, color=color, truecolor=color, columns=columns)


def enable_vt(stream: TextIO) -> bool:
    """Switch the console behind `stream` to ANSI escape processing; False when it cannot."""
    if sys.platform != "win32":
        return True
    import ctypes
    import msvcrt

    try:
        handle = msvcrt.get_osfhandle(stream.fileno())
    except (OSError, ValueError, AttributeError):
        return False
    kernel32 = ctypes.windll.kernel32
    kernel32.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    kernel32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    mode = ctypes.c_uint32()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return False
    if mode.value & VT_PROCESSING:
        return True
    return bool(kernel32.SetConsoleMode(handle, mode.value | VT_PROCESSING))


def prepare_streams() -> None:
    """On Windows a redirected stream uses the ANSI code page: make it UTF-8 and never fail."""
    if not host.is_windows():
        return
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if not isinstance(stream, io.TextIOWrapper) or stream.isatty():
            continue
        with contextlib.suppress(OSError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")
