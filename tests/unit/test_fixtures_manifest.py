# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "fixtures"
MANIFEST = json.loads((ROOT / "MANIFEST.json").read_text())


def test_every_file_matches_its_checksum() -> None:
    for conv in MANIFEST["conversations"]:
        for rel, meta in conv["files"].items():
            data = (ROOT / rel).read_bytes()
            assert len(data) == meta["bytes"], rel
            assert hashlib.sha256(data).hexdigest() == meta["sha256"], rel


def test_budget_and_total() -> None:
    total = sum(m["bytes"] for c in MANIFEST["conversations"] for m in c["files"].values())
    assert total == MANIFEST["total_bytes"]
    assert total <= 10_000_000


def test_dev_and_test_share_no_speakers() -> None:
    speakers = MANIFEST["speakers"]
    assert not set(speakers["dev"]) & set(speakers["test"])


def test_every_conversation_has_all_channel_profiles() -> None:
    for conv in MANIFEST["conversations"]:
        names = " ".join(conv["files"])
        for profile in ("phone-pstn", "phone-mobile", "voip-app", "room-recorder"):
            assert profile in names
