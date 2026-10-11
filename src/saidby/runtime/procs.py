# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import shutil
import subprocess

from saidby.errors import InputError


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
        raise InputError(f"{argv[0]} not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise InputError(f"{argv[0]} failed: {exc.stderr.strip()[-500:]}") from exc


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
