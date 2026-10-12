# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from saidby import __version__, cli
from saidby.cli import banner
from saidby.cli.banner import (
    CASSETTE_ROWS,
    MINI_ROWS,
    WORD_ROWS,
    InfoRow,
    ago,
    compact_lines,
    full_lines,
    gather_rows,
    plain_line,
    render_cells,
    show_compact,
    show_home,
)
from saidby.cli.banner_art import CASSETTE, CASSETTE_MINI, PALETTE
from saidby.cli.term import Terminal
from saidby.runtime.device import DeviceInfo
from saidby.runtime.device_cache import write_cache

TRUE = Terminal(tty=True, color=True, truecolor=True, columns=100)
ANSI = re.compile(r"\x1b\[[0-9;]*m")
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


def plain(lines: list[str]) -> list[str]:
    return [ANSI.sub("", line) for line in lines]


def test_the_art_is_well_formed() -> None:
    assert len(CASSETTE) == 16
    assert {len(row) for row in CASSETTE} == {24}
    assert len(CASSETTE_MINI) == 6
    assert {len(row) for row in CASSETTE_MINI} == {10}
    colors = {ch for row in [*CASSETTE, *CASSETTE_MINI] for ch in row} - {"."}
    assert colors <= set(PALETTE)
    assert (len(CASSETTE_ROWS), len(MINI_ROWS), len(WORD_ROWS)) == (8, 3, 4)
    assert {len(row) for row in CASSETTE_ROWS} == {24}
    assert {len(row) for row in MINI_ROWS} == {10}
    assert {len(row) for row in WORD_ROWS} == {34}


def test_half_blocks_pick_the_glyph_and_the_colors() -> None:
    red, blue = PALETTE["R"], PALETTE["B"]
    assert render_cells([(None, None)]) == " "
    assert render_cells([(red, red)]) == "\x1b[38;2;255;0;77m█\x1b[0m"
    assert render_cells([(red, None)]) == "\x1b[38;2;255;0;77m▀\x1b[0m"
    assert render_cells([(None, blue)]) == "\x1b[38;2;41;173;255m▄\x1b[0m"
    both = render_cells([(red, blue)])
    assert both == "\x1b[48;2;41;173;255m\x1b[38;2;255;0;77m▀\x1b[0m"


def test_runs_of_the_same_colors_do_not_repeat_escapes() -> None:
    red, blue = PALETTE["R"], PALETTE["B"]
    text = render_cells([(red, blue)] * 5)
    assert text.count("\x1b[") == 3
    assert text.count("▀") == 5


def test_a_gap_resets_the_colors_so_they_do_not_leak() -> None:
    red = PALETTE["R"]
    text = render_cells([(red, red), (None, None), (red, red)])
    assert text.count("\x1b[0m") == 2
    assert "█ " in ANSI.sub("", text) + " "


def test_the_full_banner_has_the_art_the_rows_and_stays_in_80_columns() -> None:
    rows = [
        InfoRow("ok", "Models", "3 default models ready"),
        InfoRow("alert", "Device", "CPU active", "details and the fix: saidby doctor"),
        InfoRow("off", "Config", "none found, using defaults"),
    ]
    lines = plain(full_lines(TRUE, rows, "run saidby init"))
    assert all(len(line) <= 80 for line in lines)
    assert lines[1].lstrip().startswith("Welcome to")
    assert "Diarized transcription · offline" in lines[6]
    assert lines[0].strip() == "┌" + " " * 74 + "┐"
    assert lines[9].strip() == "└" + " " * 74 + "┘"
    assert any(line.startswith("  ● Models") for line in lines)
    assert any(line.startswith("  ▲ Device") for line in lines)
    assert any(line.startswith("  ○ Config") for line in lines)
    assert any(line.strip() == "details and the fix: saidby doctor" for line in lines)
    assert any("Tip run saidby init" in line for line in lines)
    assert lines[-1].strip().startswith("saidby process FILE   saidby doctor   saidby --help   v")


def test_the_art_columns_line_up_on_every_row() -> None:
    lines = plain(full_lines(TRUE, []))
    for number in range(1, 9):
        assert len(lines[number]) == 78
    assert {line.index("▄") if "▄" in line else 50 for line in lines[1:2]} == {50}


def test_the_compact_banner_is_three_rows_of_cassette_and_text() -> None:
    lines = compact_lines(TRUE, "1 file · output ./saidby/", "Ctrl+C is safe")
    assert len(lines) == 3
    texts = plain(lines)
    assert texts[0].endswith("saidby " + __version__)
    assert texts[1].endswith("1 file · output ./saidby/")
    assert texts[2].endswith("Ctrl+C is safe")
    assert all(len(t) <= 80 for t in texts)


def _home(term: Terminal) -> list[str]:
    stream = io.StringIO()
    show_home(stream, term)
    return stream.getvalue().splitlines()


def test_home_shows_nothing_without_a_terminal() -> None:
    assert _home(Terminal(tty=False, color=False, truecolor=False, columns=100)) == []


def test_home_picks_the_banner_by_what_the_terminal_can_show() -> None:
    full = _home(Terminal(tty=True, color=True, truecolor=True, columns=100))
    assert len(full) > 12
    compact = _home(Terminal(tty=True, color=True, truecolor=True, columns=70))
    assert len(compact) == 3
    for narrow in (
        Terminal(tty=True, color=True, truecolor=True, columns=50),
        Terminal(tty=True, color=True, truecolor=False, columns=100),
        Terminal(tty=True, color=False, truecolor=False, columns=100),
    ):
        assert _home(narrow) == [plain_line()]


def test_a_failure_while_drawing_never_breaks_the_command(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise RuntimeError("broken")

    monkeypatch.setattr(banner, "gather_rows", boom)
    assert _home(TRUE) == []


def _compact(term: Terminal, files: int = 1) -> list[str]:
    stream = io.StringIO()
    show_compact(files, Path("saidby"), stream, term)
    return stream.getvalue().splitlines()


def test_process_gets_the_compact_banner_only_on_a_color_terminal() -> None:
    lines = _compact(TRUE)
    assert len(lines) == 4
    assert lines[3] == ""
    assert plain(lines)[1].endswith("1 file · output ./saidby/")
    assert plain(_compact(TRUE, 3))[1].endswith("3 files · output ./saidby/")
    assert _compact(Terminal(tty=False, color=False, truecolor=False, columns=100)) == []
    assert _compact(Terminal(tty=True, color=False, truecolor=False, columns=100)) == []
    assert _compact(Terminal(tty=True, color=True, truecolor=True, columns=40)) == []


def test_main_shows_the_home_banner_only_for_a_bare_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown: list[bool] = []
    monkeypatch.setattr(cli, "show_home", lambda: shown.append(True))
    monkeypatch.setattr(cli, "app", lambda: None)
    monkeypatch.setattr(sys, "argv", ["saidby"])
    cli.main()
    monkeypatch.setattr(sys, "argv", ["saidby", "doctor"])
    cli.main()
    assert shown == [True]


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (5, "just now"),
        (60, "1 minute ago"),
        (125, "2 minutes ago"),
        (3600, "1 h ago"),
        (7200 * 5, "10 h ago"),
        (86400 * 3, "3 days ago"),
    ],
)
def test_ago(seconds: int, text: str) -> None:
    assert ago(NOW - timedelta(seconds=seconds), NOW) == text


def test_the_device_row_comes_from_the_last_verdict_never_from_a_probe() -> None:
    rows, _ = gather_rows()
    device = next(r for r in rows if r.label == "Device")
    assert (device.mark, device.value) == ("off", "not checked yet")
    write_cache(DeviceInfo("cuda", "Test GPU", 8188))
    device = next(r for r in gather_rows()[0] if r.label == "Device")
    assert device.mark == "ok"
    assert device.value == "GPU active · cuda · Test GPU · 8 GB"
    assert device.detail is not None
    assert device.detail.startswith("confirmed on the last run, ")


def test_the_device_row_for_each_way_of_ending_up_on_the_cpu() -> None:
    write_cache(DeviceInfo("cpu", reason="no_gpu"))
    row = next(r for r in gather_rows()[0] if r.label == "Device")
    assert row.mark == "warn"
    assert row.value.endswith("no NVIDIA GPU found")
    write_cache(DeviceInfo("cpu", reason="gpu_unusable", note="running on CPU: x"))
    row = next(r for r in gather_rows()[0] if r.label == "Device")
    assert (row.mark, row.value) == ("alert", "CPU active · the NVIDIA GPU cannot be used")
    assert row.detail == "details and the fix: saidby doctor"


def test_the_models_row_says_when_defaults_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from saidby.models import store

    monkeypatch.setattr(store, "is_installed", lambda spec: spec.key == "asr:large-v3")
    row = next(r for r in gather_rows()[0] if r.label == "Models")
    assert row.mark == "warn"
    assert row.value == "2 of 3 default models missing"
    assert row.detail == "saidby models pull --all"
    monkeypatch.setattr(store, "is_installed", lambda spec: True)
    assert (
        next(r for r in gather_rows()[0] if r.label == "Models").value == "3 default models ready"
    )


def test_glossary_and_config_rows_describe_the_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    rows, has_config = gather_rows()
    assert not has_config
    assert [(r.label, r.mark) for r in rows if r.label in {"Glossary", "Config"}] == [
        ("Glossary", "off"),
        ("Config", "off"),
    ]
    (tmp_path / "directory.yaml").write_text(
        "version: 1\nlanguage: es\npeople:\n  - id: ana\n    name: Ana\nterms:\n  - term: Acme\n"
        "  - term: Rappi\n"
    )
    (tmp_path / "saidby.toml").write_text(
        '[saidby]\nlanguage = "es"\n[glossary]\ndirectory = "directory.yaml"\n'
    )
    rows, has_config = gather_rows()
    assert has_config
    by_label = {r.label: r for r in rows}
    assert by_label["Glossary"].value == "./directory.yaml · 1 person · 2 terms"
    assert by_label["Config"].value == "./saidby.toml · es · output ./saidby/"


def test_a_broken_config_shows_up_as_an_alert_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "saidby.toml").write_text("this is not toml")
    rows, has_config = gather_rows()
    config = next(r for r in rows if r.label == "Config")
    assert config.mark == "alert"
    assert "not valid TOML" in config.value
    assert not has_config
