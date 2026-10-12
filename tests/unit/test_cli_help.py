# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import typer.main
from typer.testing import CliRunner

from saidby.cli import app

runner = CliRunner()


def _walk(command: Any, path: str) -> list[tuple[str, Any]]:
    found = [(path, command)]
    for name, sub in getattr(command, "commands", {}).items():
        found += _walk(sub, f"{path} {name}")
    return found


def _all_commands() -> list[tuple[str, Any]]:
    return _walk(typer.main.get_command(app), "saidby")


def test_every_command_has_a_description() -> None:
    missing = [path for path, cmd in _all_commands() if not (cmd.help or "").strip()]
    assert missing == []


def test_every_option_and_argument_is_documented() -> None:
    skipped = {"--install-completion", "--show-completion"}
    missing = []
    for path, cmd in _all_commands():
        for param in cmd.params:
            opts = getattr(param, "opts", None)
            if not opts or set(opts) & skipped or not param.name:
                continue
            if not (getattr(param, "help", None) or "").strip():
                missing.append(f"{path} {opts}")
    assert missing == []


def test_short_help_flag_works_everywhere() -> None:
    for path, _ in _all_commands():
        args = [*path.split()[1:], "-h"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0, path
        assert "Usage" in result.output, path


def test_top_level_help_is_grouped_and_has_examples() -> None:
    out = runner.invoke(app, ["--help"]).output
    for panel in ("Transcribe", "After a run", "Set up", "Measure"):
        assert panel in out
    assert "saidby doctor" in out
    assert out.index("process") < out.index("doctor") < out.index("eval")


def test_process_options_are_grouped() -> None:
    out = runner.invoke(app, ["process", "--help"]).output
    for panel in ("Input and output", "Speech recognition", "Speakers", "Glossary and correction"):
        assert panel in out
    assert "Examples:" in out
