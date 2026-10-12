# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TextIO

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


def detect(stream: TextIO, environ: Mapping[str, str] | None = None) -> Terminal:
    env = os.environ if environ is None else environ
    tty = stream.isatty() and env.get("TERM", "") not in {"", "dumb"}
    color = tty and not env.get("NO_COLOR")
    columns = shutil.get_terminal_size(fallback=(80, 24)).columns if tty else 80
    return Terminal(
        tty=tty,
        color=color,
        truecolor=color and env.get("COLORTERM", "").lower() in TRUECOLOR_VALUES,
        columns=columns,
    )
