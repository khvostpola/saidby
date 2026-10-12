# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path

import pytest

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["PYANNOTE_METRICS_ENABLED"] = "false"


@pytest.fixture(autouse=True)
def isolated_user_config(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    home = tmp_path_factory.mktemp("user")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / "cache"))
    for name in [key for key in os.environ if key.startswith("SAIDBY_")]:
        monkeypatch.delenv(name)
    return home
