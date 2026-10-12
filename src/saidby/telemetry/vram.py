# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import subprocess
import threading
from types import TracebackType


class VramPeak:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.peak: int | None = None
        self._proc: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "VramPeak":
        if not self.enabled:
            return self
        try:
            self._proc = subprocess.Popen(
                [
                    "nvidia-smi",
                    "--query-compute-apps=pid,used_memory",
                    "--format=csv,noheader,nounits",
                    "-lms",
                    "250",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return self
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()
        return self

    def _read(self) -> None:
        assert self._proc is not None
        assert self._proc.stdout is not None
        pid = str(os.getpid())
        for line in self._proc.stdout:
            fields = [f.strip() for f in line.split(",")]
            if len(fields) == 2 and fields[0] == pid and fields[1].isdigit():
                self.peak = max(self.peak or 0, int(fields[1]))

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait()
        if self._thread is not None:
            self._thread.join(timeout=1)
