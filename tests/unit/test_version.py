# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import subprocess
import tomllib
from pathlib import Path

import saidby


def test_version_matches_pyproject() -> None:
    root = Path(__file__).resolve().parents[2]
    declared = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    assert saidby.__version__ == declared


def test_cli_version() -> None:
    out = subprocess.run(
        ["saidby", "--version"], check=True, capture_output=True, text=True, encoding="utf-8"
    )
    assert out.stdout.strip() == saidby.__version__
