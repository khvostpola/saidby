# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import shutil
import subprocess
from pathlib import Path

from saidby.errors import InputError
from saidby.i18n import _


def run_checked(
    argv: list[str], *, timeout: float | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise InputError(_("{argv} not found on PATH").format(argv=argv[0])) from exc
    except subprocess.CalledProcessError as exc:
        raise InputError(
            _("{argv} failed: {value}").format(argv=argv[0], value=exc.stderr.strip()[-500:])
        ) from exc


def which(name: str) -> str | None:
    return shutil.which(name)


def tool_version(name: str, flag: str = "-version") -> str | None:
    if which(name) is None:
        return None
    try:
        out = run_checked([name, flag], timeout=10).stdout
    except InputError:
        return None
    return out.splitlines()[0].strip() if out else None


def ffplay_argv(path: Path, start: float, duration: float) -> list[str]:
    return [
        "ffplay",
        "-nodisp",
        "-autoexit",
        "-loglevel",
        "quiet",
        "-ss",
        f"{start:.2f}",
        "-t",
        f"{duration:.2f}",
        str(path),
    ]


def play(path: Path, start: float, duration: float) -> bool:
    if which("ffplay") is None:
        return False
    process = subprocess.Popen(
        ffplay_argv(path, start, duration),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait(timeout=2)
    return True
