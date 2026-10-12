# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path
from typing import Annotated

import typer

from saidby.cli.term import Terminal, detect
from saidby.config.settings import Settings
from saidby.errors import UsageError
from saidby.formats.corrections_log import read_corrections, write_corrections
from saidby.formats.directory_yaml import load_directory, save_directory
from saidby.i18n import _, ngettext
from saidby.review.apply import apply_speaker, apply_text, resolve_speaker
from saidby.review.context import (
    audio_source,
    context_of,
    find_overlap,
    play_window,
    repeated_words,
    strip_overlap,
)
from saidby.review.queue import DEFAULT_LOW_P, KINDS, Item, build_queue, log_decision
from saidby.review.suggest import apply_suggestions, suggest_variants
from saidby.runtime.procs import play
from saidby.schema.correction import Correction
from saidby.speakers.remap import Folder

QUESTION_WIDTH = 40


def _speakers(folder: Folder, item: Item) -> str:
    words = folder.transcript.words()[item.first : item.last + 1]
    return " -> ".join(dict.fromkeys(w.speaker or "?" for w in words))


def _decide(folder: Folder, item: Item, answer: str) -> tuple[Correction | None, str | None]:
    speaker: str | None = None
    if answer.startswith("@"):
        name, _sep, answer = answer[1:].partition(" ")
        speaker = resolve_speaker(folder.transcript.speakers, name)
        folder.transcript = apply_speaker(folder.transcript, item, speaker)
    correction = None
    text = answer.strip()
    if text:
        text = _without_repeats(folder, item, text)
        folder.transcript, correction = apply_text(folder.transcript, item, text)
    return correction, speaker


def _without_repeats(folder: Folder, item: Item, text: str) -> str:
    overlap = find_overlap(folder.transcript, item, text)
    if not overlap:
        return text
    repeated = repeated_words(text, overlap)
    question = _('Your text repeats "{repeated}" from next to the span. Replace only the span?')
    question = question.format(repeated=repeated)
    return strip_overlap(text, overlap) if typer.confirm(question, default=True) else text


def _show(folder: Folder, item: Item, number: int, total: int, term: Terminal) -> str:
    context = context_of(folder.transcript, item)
    paint = term.paint
    parts = []
    if context.before:
        parts.append(paint(("… " if context.more_before else "") + context.before, "dim"))
    parts.append(f"[{paint(context.span, 'bold', 'yellow')}]")
    if context.after:
        parts.append(paint(context.after + (" …" if context.more_after else ""), "dim"))
    typer.echo(
        f"\n[{number}/{total}] {item.kind} · {item.start:.1f}-{item.end:.1f} s · "
        f"{_speakers(folder, item)}\n  {' '.join(parts)}"
    )
    shown = context.span
    if len(shown) > QUESTION_WIDTH:
        shown = shown[: QUESTION_WIDTH - 1] + "…"
    return _('Text for "{span}"?').format(span=shown)


def _play(folder: Folder, item: Item) -> None:
    source = audio_source(folder.out_dir, folder.transcript, folder.manifest, item)
    if source is None:
        typer.echo(_("no audio to play: there is no work folder, track or original recording"))
        return
    start, duration = play_window(item)
    if not play(source.path, start, duration):
        typer.echo(
            _("ffplay not found; open {path} at {start:.1f} s").format(
                path=source.path, start=start
            )
        )


def review(
    out_dir: Annotated[
        Path,
        typer.Argument(help="Output folder of a finished run (the one `saidby process` wrote)."),
    ],
    kinds: Annotated[str, typer.Option(help="Comma list of: " + ", ".join(KINDS))] = ",".join(
        KINDS
    ),
    low_confidence: Annotated[
        float, typer.Option(help="Reviewed when word probability is below")
    ] = DEFAULT_LOW_P,
    limit: Annotated[int | None, typer.Option(min=1, help="Review at most this many spans")] = None,
    directory: Annotated[
        Path | None,
        typer.Option(help="Offer to add new variants here (default: the last configured file)"),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Accept directory suggestions")] = False,
) -> None:
    """Review uncertain spans of a finished run and fix them by typing the right text.

    This is the one command that prints transcript text on the terminal.
    """
    chosen = tuple(k.strip() for k in kinds.split(",") if k.strip())
    unknown = [k for k in chosen if k not in KINDS]
    if unknown:
        raise UsageError(
            _("unknown kinds {unknown}; valid: {items}").format(
                unknown=unknown, items=", ".join(KINDS)
            )
        )
    folder = Folder(out_dir)
    queue = build_queue(
        out_dir, folder.transcript, folder.manifest, kinds=chosen, low_p=low_confidence
    )
    if limit:
        queue = queue[:limit]
    if not queue:
        typer.echo(_("nothing to review"))
        return
    typer.echo(
        _(
            "Enter keeps the text; type the corrected text to replace it; p plays the span; "
            "@SPEAKER (optionally followed by text) sets who spoke; /s skips; /q quits"
        )
    )
    new_corrections: list[Correction] = []
    changed = False
    try:
        term = detect(sys.stdout)
        for number, item in enumerate(queue, 1):
            question = _show(folder, item, number, len(queue), term)
            answer = _ask(question)
            while answer in {"p", "/p"}:
                _play(folder, item)
                answer = _ask(question)
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
    finally:
        if changed:
            _save(folder, new_corrections)
    typer.echo("")
    saved = ngettext(
        "saved {n} text correction", "saved {n} text corrections", len(new_corrections)
    )
    typer.echo(saved.format(n=len(new_corrections)))
    configured = Settings.load().directory
    target = directory or (configured[-1] if configured else None)
    if target is not None and new_corrections:
        _offer_directory(target, new_corrections, yes)


def _ask(question: str) -> str:
    try:
        answer: str = typer.prompt(question, default="", show_default=False)
    except typer.Abort:
        if sys.stdin.isatty():
            raise
        raise UsageError(
            _(
                "the input ended before the review did: run saidby review in a terminal, "
                "or pipe one answer per line (/q quits)"
            )
        ) from None
    return answer.strip()


def _save(folder: Folder, new_corrections: list[Correction]) -> None:
    if new_corrections:
        log = folder.out_dir / "corrections.jsonl"
        write_corrections(log, [*read_corrections(log), *new_corrections])
    folder.save({"op": "review", "edited": str(len(new_corrections))})


def _offer_directory(path: Path, corrections: list[Correction], yes: bool) -> None:
    model, raw = load_directory(path)
    suggestions = suggest_variants(model, corrections)
    if not suggestions:
        return
    for s in suggestions:
        typer.echo(
            _("  {target}: add variant {variant!r}").format(target=s.target, variant=s.variant)
        )
    if yes or typer.confirm(_("Add these variants to the directory?"), default=False):
        count = apply_suggestions(raw, suggestions)
        backup = save_directory(path, raw)
        added = ngettext("added {n} variant", "added {n} variants", count).format(n=count)
        typer.echo(added + (_(" (backup: {backup})").format(backup=backup) if backup else ""))
