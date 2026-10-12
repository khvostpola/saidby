# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
import time
from pathlib import Path

import pytest

from saidby.cli.paths import show_path, typed_path, unquote
from saidby.config.writer import display_path, portable_path
from saidby.formats.yaml_io import save_yaml
from saidby.runtime import host
from saidby.speakers.remap import _rename_track


def test_config_and_cache_folders_follow_the_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAIDBY_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("SAIDBY_CACHE_DIR", str(tmp_path / "cache"))
    assert host.config_dir() == tmp_path / "cfg"
    assert host.cache_dir() == tmp_path / "cache"


@pytest.mark.skipif(host.is_windows(), reason="XDG folders are a POSIX convention")
def test_without_overrides_the_folders_follow_xdg(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SAIDBY_CONFIG_DIR")
    monkeypatch.delenv("SAIDBY_CACHE_DIR")
    assert host.config_dir() == isolated_home / "config" / "saidby"
    assert host.cache_dir() == isolated_home / "cache" / "saidby"


def test_quoting_for_posix_shells(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host, "is_windows", lambda: False)
    assert host.quote("call.m4a") == "call.m4a"
    assert host.quote("my call.m4a") == "'my call.m4a'"
    assert host.join(["saidby", "process", "my call.m4a"]) == "saidby process 'my call.m4a'"


def test_quoting_for_powershell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host, "is_windows", lambda: True)
    assert host.quote(r"C:\calls\call.m4a") == r"C:\calls\call.m4a"
    assert host.quote("my call.m4a") == "'my call.m4a'"
    assert host.quote("O'Brien.m4a") == "'O''Brien.m4a'"
    assert host.quote("a&b.m4a") == "'a&b.m4a'"
    assert host.quote("cost$5.m4a") == "'cost$5.m4a'"
    assert host.quote("") == "''"
    assert host.join(["saidby", "review", r"out\call 1"]) == "saidby review 'out\\call 1'"


def test_the_system_language_is_only_read_on_windows() -> None:
    language = host.system_language()
    if host.is_windows():
        assert language is None or 2 <= len(language) <= 3
    else:
        assert language is None


def test_quotes_around_typed_paths_are_dropped() -> None:
    assert unquote('"C:\\calls\\my call.m4a"') == "C:\\calls\\my call.m4a"
    assert unquote(" 'call.m4a' ") == "call.m4a"
    assert unquote('"') == '"'
    assert unquote("plain.m4a") == "plain.m4a"
    assert typed_path(' "~/x.yaml" ') == Path("~/x.yaml").expanduser()


def test_portable_paths_use_slashes_and_shown_paths_the_native_separator(
    isolated_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inside = isolated_home / "docs" / "team.yaml"
    assert portable_path(inside) == "~/docs/team.yaml"
    assert display_path(inside) == str(Path("~") / "docs" / "team.yaml")
    outside = tmp_path / "team.yaml"
    assert portable_path(outside) == outside.as_posix()
    assert display_path(outside) == str(outside)
    monkeypatch.chdir(tmp_path)
    assert show_path(tmp_path / "saidby.toml") == "." + os.sep + "saidby.toml"


def test_saving_yaml_retries_while_the_file_is_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts: list[int] = []
    real_replace = os.replace

    def flaky(src: str, dst: str) -> None:
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError("held by another program")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    save_yaml(tmp_path / "d.yaml", {"a": 1}, backup=False)
    assert (tmp_path / "d.yaml").read_text(encoding="utf-8") == "a: 1\n"
    assert len(attempts) == 3


def test_saving_yaml_gives_up_after_three_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def held(src: str, dst: str) -> None:
        raise PermissionError("held by another program")

    monkeypatch.setattr(os, "replace", held)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    with pytest.raises(PermissionError):
        save_yaml(tmp_path / "d.yaml", {"a": 1}, backup=False)


def test_a_case_only_rename_goes_through_a_staging_name(tmp_path: Path) -> None:
    old = tmp_path / "ana.flac"
    old.write_bytes(b"x")
    _rename_track(old, tmp_path / "Ana.flac")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Ana.flac"]
    _rename_track(tmp_path / "Ana.flac", tmp_path / "ana-gomez.flac")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ana-gomez.flac"]
