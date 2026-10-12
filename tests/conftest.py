# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from saidby.i18n import set_language


def _default_hf_home() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return str(Path(base) / "huggingface")


os.environ.setdefault("HF_HOME", _default_hf_home())
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["PYANNOTE_METRICS_ENABLED"] = "false"


@pytest.fixture
def set_home(monkeypatch: pytest.MonkeyPatch) -> Callable[[Path], None]:
    def apply(path: Path) -> None:
        monkeypatch.setenv("HOME", str(path))
        monkeypatch.setenv("USERPROFILE", str(path))

    return apply


@pytest.fixture(autouse=True)
def isolated_home(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    set_home: Callable[[Path], None],
) -> Path:
    home = tmp_path_factory.mktemp("user")
    set_home(home)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / "cache"))
    for name in [key for key in os.environ if key.startswith("SAIDBY_")]:
        monkeypatch.delenv(name)
    monkeypatch.setenv("SAIDBY_CONFIG_DIR", str(home / "config" / "saidby"))
    monkeypatch.setenv("SAIDBY_CACHE_DIR", str(home / "cache" / "saidby"))
    return home


@pytest.fixture(autouse=True)
def english_messages(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("SAIDBY_UI_LANG", "en")
    set_language("en")
    yield
    set_language("en")
