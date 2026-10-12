# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

"""What depends on the operating system: folders, quoting, the system language.

Pure-Python branches ask `is_windows()`; calls into Windows APIs stay inside literal
`sys.platform == "win32"` blocks so that mypy can check both platforms.
"""

import contextlib
import os
import platform
import re
import shlex
import sys
from collections.abc import Iterable
from pathlib import Path

from platformdirs import user_cache_path, user_config_path

APP = "saidby"
ENV_CONFIG_DIR = "SAIDBY_CONFIG_DIR"
ENV_CACHE_DIR = "SAIDBY_CACHE_DIR"
PYTORCH_CUDA_INDEX = "https://download.pytorch.org/whl/cu130"
SUPPORTED = {"linux", "win32"}
_POWERSHELL_PLAIN = re.compile(r"[\w@%+=:,./\\-]+")
_LOCALE_NAME_MAX = 85


def is_windows() -> bool:
    return sys.platform == "win32"


def is_supported() -> bool:
    return sys.platform in SUPPORTED


def platform_label() -> str:
    """`Fedora Linux 43 (Workstation Edition) x86_64` or `Windows 11 (10.0.26100) AMD64`."""
    if is_windows():
        return f"Windows {platform.release()} ({platform.version()}) {platform.machine()}"
    name = f"{platform.system()} {platform.release()}"
    if sys.platform == "linux":
        with contextlib.suppress(OSError):
            name = platform.freedesktop_os_release().get("PRETTY_NAME", name)
    return f"{name} {platform.machine()}"


def gpu_install_command() -> str:
    """How to install saidby so that it can use an NVIDIA GPU on this system.

    PyPI's PyTorch is a CUDA build on Linux and a CPU build on Windows, where the CUDA wheel
    lives on PyTorch's own index.
    """
    base = 'uv tool install "saidby[cuda]"'
    if is_windows():
        return f"{base} --index {PYTORCH_CUDA_INDEX} --index-strategy unsafe-best-match"
    return base


def ffmpeg_install_hint() -> str:
    return "winget install ffmpeg" if is_windows() else "sudo dnf install ffmpeg"


def config_dir() -> Path:
    explicit = os.environ.get(ENV_CONFIG_DIR)
    if explicit:
        return Path(explicit).expanduser()
    return user_config_path(APP, appauthor=False, roaming=True)


def cache_dir() -> Path:
    explicit = os.environ.get(ENV_CACHE_DIR)
    if explicit:
        return Path(explicit).expanduser()
    return user_cache_path(APP, appauthor=False)


def quote(arg: str) -> str:
    """Quote one argument for the shell the user is likely pasting into.

    POSIX shells get `shlex` quoting; Windows gets PowerShell's single-quoted literal.
    """
    if not is_windows():
        return shlex.quote(arg)
    if arg and _POWERSHELL_PLAIN.fullmatch(arg):
        return arg
    return "'" + arg.replace("'", "''") + "'"


def join(argv: Iterable[str]) -> str:
    return " ".join(quote(arg) for arg in argv)


def system_language() -> str | None:
    """The two-letter language of the Windows user locale, such as `es` for `es-CO`.

    Returns None elsewhere: POSIX callers read `LANG` and friends themselves.
    """
    if sys.platform != "win32":
        return None
    import ctypes

    buffer = ctypes.create_unicode_buffer(_LOCALE_NAME_MAX)
    if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, _LOCALE_NAME_MAX) == 0:
        return None
    match = re.match(r"([A-Za-z]{2,3})(?:[-_]|$)", buffer.value)
    return match.group(1).lower() if match else None
