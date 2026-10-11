# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

from saidby.schema.export import SCHEMAS, render

ROOT = Path(__file__).resolve().parents[2] / "schemas"


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_committed_schema_is_current(name: str) -> None:
    assert (ROOT / f"{name}.schema.json").read_text() == render(name)
