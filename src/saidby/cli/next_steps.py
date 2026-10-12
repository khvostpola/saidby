# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import shlex
from dataclasses import dataclass
from pathlib import Path

from saidby.cli.term import Terminal
from saidby.formats.manifest import read_manifest
from saidby.formats.words_json import read_transcript
from saidby.i18n import _, ngettext
from saidby.review.queue import build_queue

LABEL_WIDTH = 9


@dataclass(frozen=True)
class FolderState:
    out_dir: Path
    unnamed: tuple[str, ...]
    doubtful: int


def read_state(out_dir: Path) -> FolderState | None:
    try:
        manifest = read_manifest(out_dir / "manifest.json")
        transcript = read_transcript(out_dir / "transcript.words.json")
        queue = build_queue(out_dir, transcript, manifest)
    except Exception:
        return None
    unnamed = tuple(s.label for s in transcript.speakers if not s.name)
    return FolderState(out_dir, unnamed, len(queue))


def _line(label: str, command: str, note: str, term: Terminal) -> str:
    head = term.paint(f"{label}:".ljust(LABEL_WIDTH), "dim")
    tail = f"   {term.paint(note, 'dim')}" if note else ""
    return f"  {head} {command}{tail}"


def next_steps(states: list[FolderState], term: Terminal) -> list[str]:
    needing_names = [s for s in states if s.unnamed]
    needing_review = [s for s in states if s.doubtful]
    lines: list[str] = []
    if needing_names:
        first = needing_names[0]
        quoted = shlex.quote(str(first.out_dir))
        command = term.paint(f"saidby speakers map {quoted} --set {first.unnamed[0]}=NAME", "cyan")
        count = len(needing_names)
        many = ngettext(
            "{n} folder has speakers without names",
            "{n} folders have speakers without names",
            count,
        ).format(n=count)
        lines.append(_line(_("name"), command, many if len(states) > 1 else "", term))
    if needing_review:
        first = needing_review[0]
        command = term.paint(f"saidby review {shlex.quote(str(first.out_dir))}", "cyan")
        spans = sum(s.doubtful for s in needing_review)
        note = ngettext("{n} doubtful span", "{n} doubtful spans", spans).format(n=spans)
        lines.append(_line(_("review"), command, note, term))
    return lines
