# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import subprocess
import sys

import pytest

from saidby.runtime import host
from saidby.runtime.procs import spawn_managed

SLEEP = [sys.executable, "-c", "import time; time.sleep(30)"]


@pytest.mark.skipif(host.is_windows(), reason="sessions are a POSIX concept")
def test_a_managed_helper_gets_its_own_session_on_posix() -> None:
    proc = spawn_managed(SLEEP, stdout=subprocess.DEVNULL)
    try:
        if sys.platform != "win32":
            assert os.getsid(proc.pid) == proc.pid
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.mark.skipif(not host.is_windows(), reason="the Windows branch of spawn_managed")
def test_a_managed_helper_starts_and_stops_on_windows() -> None:
    proc = spawn_managed(SLEEP, stdout=subprocess.DEVNULL)
    assert proc.poll() is None
    proc.terminate()
    proc.wait(timeout=10)
    assert proc.poll() is not None
