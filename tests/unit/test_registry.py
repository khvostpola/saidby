# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import dataclasses
from pathlib import Path

import pytest

from saidby.errors import UsageError
from saidby.models.registry import REGISTRY, get_spec, render_markdown


def test_model_licenses_file_is_in_sync() -> None:
    path = Path(__file__).resolve().parents[2] / "MODEL_LICENSES.md"
    assert path.read_text(encoding="utf-8") == render_markdown()


def test_default_must_allow_commercial_use() -> None:
    with pytest.raises(ValueError, match="commercial"):
        dataclasses.replace(REGISTRY[0], default=True, commercial_ok=False)


def test_revisions_are_full_shas() -> None:
    assert all(len(s.revision) == 40 for s in REGISTRY)


def test_unknown_key_is_usage_error() -> None:
    with pytest.raises(UsageError):
        get_spec("asr:nope")


def test_keys_are_unique() -> None:
    keys = [s.key for s in REGISTRY]
    assert len(keys) == len(set(keys))
