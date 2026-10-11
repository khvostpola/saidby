# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from saidby.schema.transcript import Transcript


def write_transcript(path: Path, transcript: Transcript) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(transcript.model_dump_json(by_alias=True, indent=1), encoding="utf-8")


def read_transcript(path: Path) -> Transcript:
    return Transcript.model_validate_json(path.read_text(encoding="utf-8"))
