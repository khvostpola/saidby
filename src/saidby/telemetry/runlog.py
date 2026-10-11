# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime
from pathlib import Path


class RunLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, level: str, stage: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} {level} {stage}: {message}\n")

    def note(self, stage: str, message: str) -> None:
        self.write("INFO", stage, message)

    def caution(self, stage: str, message: str) -> None:
        self.write("WARN", stage, message)

    def fail(self, stage: str, message: str) -> None:
        self.write("ERROR", stage, message)
