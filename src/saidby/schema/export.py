# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

from pydantic import BaseModel

from saidby.schema.diarization import Diarization
from saidby.schema.directory import Directory
from saidby.schema.manifest import Manifest
from saidby.schema.transcript import Transcript

SCHEMAS: dict[str, type[BaseModel]] = {
    "directory-1": Directory,
    "words-1": Transcript,
    "manifest-1": Manifest,
    "diarization-1": Diarization,
}


def render(name: str) -> str:
    return json.dumps(SCHEMAS[name].model_json_schema(by_alias=True), indent=2) + "\n"


def write_all(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in SCHEMAS:
        (folder / f"{name}.schema.json").write_text(render(name), encoding="utf-8", newline="\n")


def main() -> None:
    write_all(Path("schemas"))


if __name__ == "__main__":
    main()
