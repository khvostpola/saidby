# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Annotated

import typer

from saidby.errors import UsageError
from saidby.formats.corrections_log import read_corrections, write_corrections
from saidby.formats.directory_yaml import load_directory, save_directory
from saidby.review.apply import apply_speaker, apply_text, resolve_speaker, span_text
from saidby.review.queue import DEFAULT_LOW_P, KINDS, Item, build_queue, log_decision
from saidby.review.suggest import apply_suggestions, suggest_variants
from saidby.schema.correction import Correction
from saidby.speakers.remap import Folder

HELP = (
    "Enter keeps the text; type the corrected text to replace it; "
    "@SPEAKER (optionally followed by text) sets who spoke; /s skips; /q quits"
)


def _speakers(folder: Folder, item: Item) -> str:
    words = folder.transcript.words()[item.first : item.last + 1]
    return " -> ".join(dict.fromkeys(w.speaker or "?" for w in words))


def _decide(folder: Folder, item: Item, answer: str) -> tuple[Correction | None, str | None]:
    speaker: str | None = None
    if answer.startswith("@"):
        name, _, answer = answer[1:].partition(" ")
        speaker = resolve_speaker(folder.transcript.speakers, name)
        folder.transcript = apply_speaker(folder.transcript, item, speaker)
    correction = None
    if answer.strip():
        folder.transcript, correction = apply_text(folder.transcript, item, answer.strip())
    return correction, speaker


def review(
    out_dir: Path,
    kinds: Annotated[str, typer.Option(help="Comma list of: " + ", ".join(KINDS))] = ",".join(
        KINDS
    ),
    low_confidence: Annotated[
        float, typer.Option(help="Reviewed when word probability is below")
    ] = DEFAULT_LOW_P,
    limit: Annotated[int | None, typer.Option(min=1, help="Review at most this many spans")] = None,
    directory: Annotated[Path | None, typer.Option(help="Offer to add new variants here")] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Accept directory suggestions")] = False,
) -> None:
    """Review uncertain spans of a finished run and fix them by typing the right text.

    This is the one command that prints transcript text on the terminal.
    """
    chosen = tuple(k.strip() for k in kinds.split(",") if k.strip())
    unknown = [k for k in chosen if k not in KINDS]
    if unknown:
        raise UsageError(f"unknown kinds {unknown}; valid: {', '.join(KINDS)}")
    folder = Folder(out_dir)
    queue = build_queue(
        out_dir, folder.transcript, folder.manifest, kinds=chosen, low_p=low_confidence
    )
    if limit:
        queue = queue[:limit]
    if not queue:
        typer.echo("nothing to review")
        return
    typer.echo(HELP)
    new_corrections: list[Correction] = []
    changed = False
    for number, item in enumerate(queue, 1):
        typer.echo(
            f"\n[{number}/{len(queue)}] {item.kind} · {item.start:.1f}-{item.end:.1f} s · "
            f"{_speakers(folder, item)}\n  {span_text(folder.transcript, item)}"
        )
        answer = typer.prompt(">", default="", show_default=False).strip()
        if answer == "/q":
            break
        if answer == "/s":
            continue
        correction, speaker = _decide(folder, item, answer)
        if correction is not None:
            new_corrections.append(correction)
            log_decision(out_dir, item, "edited", speaker)
        else:
            log_decision(out_dir, item, "speaker" if speaker else "kept", speaker)
        changed = changed or correction is not None or speaker is not None
    if changed:
        if new_corrections:
            existing = read_corrections(out_dir / "corrections.jsonl")
            write_corrections(out_dir / "corrections.jsonl", [*existing, *new_corrections])
        folder.save({"op": "review", "edited": str(len(new_corrections))})
    typer.echo(f"\nsaved {len(new_corrections)} text corrections")
    if directory is not None and new_corrections:
        _offer_directory(directory, new_corrections, yes)


def _offer_directory(path: Path, corrections: list[Correction], yes: bool) -> None:
    model, raw = load_directory(path)
    suggestions = suggest_variants(model, corrections)
    if not suggestions:
        return
    for s in suggestions:
        typer.echo(f"  {s.target}: add variant {s.variant!r}")
    if yes or typer.confirm("Add these variants to the directory?", default=False):
        count = apply_suggestions(raw, suggestions)
        backup = save_directory(path, raw)
        typer.echo(f"added {count} variants" + (f" (backup: {backup})" if backup else ""))
