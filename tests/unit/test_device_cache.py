# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from saidby.runtime import device_cache, host
from saidby.runtime.device import DeviceInfo
from saidby.runtime.device_cache import cache_path, read_cache, write_cache

MOMENT = datetime(2026, 10, 12, 8, 30, tzinfo=UTC)


def test_the_cache_lives_in_the_user_cache_folder(isolated_home: Path) -> None:
    assert cache_path() == host.cache_dir() / "device.json"
    assert cache_path() == isolated_home / "cache" / "saidby" / "device.json"


@pytest.mark.skipif(host.is_windows(), reason="XDG folders are a POSIX convention")
def test_empty_xdg_cache_home_falls_back_to_dot_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, set_home: Callable[[Path], None]
) -> None:
    monkeypatch.delenv("SAIDBY_CACHE_DIR")
    monkeypatch.setenv("XDG_CACHE_HOME", "")
    set_home(tmp_path)
    assert cache_path() == tmp_path / ".cache" / "saidby" / "device.json"


def test_nothing_cached_means_no_verdict() -> None:
    assert read_cache() is None


def test_a_verdict_round_trips() -> None:
    write_cache(DeviceInfo("cuda", "Test GPU", 8188), MOMENT)
    cached = read_cache()
    assert cached is not None
    assert (cached.kind, cached.name, cached.vram_total_mb, cached.reason) == (
        "cuda",
        "Test GPU",
        8188,
        None,
    )
    assert cached.checked_at == MOMENT


def test_the_reason_for_cpu_is_kept() -> None:
    write_cache(DeviceInfo("cpu", reason="gpu_unusable", note="running on CPU: x"), MOMENT)
    cached = read_cache()
    assert cached is not None
    assert (cached.kind, cached.reason) == ("cpu", "gpu_unusable")


@pytest.mark.parametrize("body", ["not json", "[]", '{"schema": "other/1"}', "{}"])
def test_a_damaged_file_is_no_verdict(body: str) -> None:
    path = cache_path()
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    assert read_cache() is None


def test_a_verdict_from_another_version_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    write_cache(DeviceInfo("cuda", "Test GPU", 8188), MOMENT)
    monkeypatch.setattr(device_cache, "__version__", "9.9.9")
    assert read_cache() is None


def test_writing_never_fails_when_the_folder_is_not_writable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where a folder should be", encoding="utf-8")
    monkeypatch.setenv("SAIDBY_CACHE_DIR", str(blocker))
    write_cache(DeviceInfo("cpu", reason="no_gpu"))
    assert read_cache() is None


def test_the_file_is_small_plain_json() -> None:
    write_cache(DeviceInfo("cpu", reason="no_gpu"), MOMENT)
    data = json.loads(cache_path().read_text(encoding="utf-8"))
    assert data["schema"] == "saidby.device/1"
    assert set(data) == {
        "schema",
        "saidby",
        "checked_at",
        "kind",
        "name",
        "vram_total_mb",
        "reason",
    }
