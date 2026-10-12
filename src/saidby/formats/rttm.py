# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from saidby.schema.diarization import Turn


def format_rttm(uri: str, turns: list[Turn]) -> str:
    return "".join(
        f"SPEAKER {uri} 1 {t.start:.3f} {t.end - t.start:.3f} <NA> <NA> {t.label} <NA> <NA>\n"
        for t in sorted(turns, key=lambda t: (t.start, t.label))
    )


def write_rttm(path: Path, uri: str, turns: list[Turn]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_rttm(uri, turns), encoding="utf-8", newline="\n")


def parse_rttm(text: str) -> list[Turn]:
    turns = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 8 or fields[0] != "SPEAKER":
            continue
        start = float(fields[3])
        turns.append(Turn(start=start, end=start + float(fields[4]), label=fields[7]))
    return turns


def read_rttm(path: Path) -> list[Turn]:
    return parse_rttm(path.read_text(encoding="utf-8"))
