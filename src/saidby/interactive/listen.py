# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable
from enum import Enum
from pathlib import Path

from saidby.cli.ui import Ui
from saidby.i18n import _
from saidby.runtime.procs import play
from saidby.speakers.remap import Folder
from saidby.speakers.samples import Sample, clean_samples, turn_counts

Player = Callable[[Path, float, float], bool]
KEYS = {"", "p", "s", "q"}


class Step(Enum):
    CONTINUE = "continue"
    SKIP = "skip"
    QUIT = "quit"


def clock(seconds: float) -> str:
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes:02d}:{rest:02d}"


def sample_text(sample: Sample | None) -> str:
    return "-" if sample is None else f"{clock(sample.start)}-{clock(sample.end)}"


def speaker_table(folder: Folder, samples: dict[str, Sample]) -> list[str]:
    counts = turn_counts(folder.turns)
    header = [_("voice"), _("speech"), _("turns"), _("clean sample"), _("track")]
    body = [
        [
            s.label,
            clock(s.speech_s),
            str(counts.get(s.label, 0)),
            sample_text(samples.get(s.label)),
            s.track or "-",
        ]
        for s in folder.transcript.speakers
    ]
    widths = [max(len(row[i]) for row in [header, *body]) for i in range(len(header))]
    lines = [
        "  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)) for row in [header, *body]
    ]
    return [f"  {line.rstrip()}" for line in lines]


def _play_all(ui: Ui, folder: Folder, samples: dict[str, Sample], player: Player) -> None:
    paint = ui.term.paint
    for entry in folder.transcript.speakers:
        sample = samples.get(entry.label)
        if sample is None or not entry.track:
            continue
        path = folder.out_dir / entry.track
        ui.say(f"  {paint('▶', 'blue')} {entry.label}  {sample_text(sample)}")
        if not player(path, sample.start, sample.duration):
            hint = paint(_("ffplay not found, open this file instead:"), "dim")
            ui.say(f"    {hint} {path}")


def _keys_line(ui: Ui) -> str:
    keys = [
        ("Enter", _("I listened, continue")),
        ("p", _("play a sample")),
        ("s", _("skip naming")),
        ("q", _("quit")),
    ]
    paint = ui.term.paint
    return "  " + "   ".join(f"{paint(key, 'bold')} {paint(text, 'dim')}" for key, text in keys)


def listen(ui: Ui, folder: Folder, *, title: str, player: Player = play) -> Step:
    paint = ui.term.paint
    samples = clean_samples(folder.turns)
    ui.say()
    ui.say(paint(title, "bold"))
    ui.say(paint(_("Each track holds only that person's speech. Listen before naming."), "dim"))
    ui.say()
    for line in speaker_table(folder, samples):
        ui.say(line)
    ui.say()
    url = (folder.out_dir.resolve() / "speakers").as_uri()
    ui.say(f"  {paint(_('Folder'), 'dim')}  {paint(url, 'cyan')}")
    ui.say()
    ui.say(_keys_line(ui))

    def valid(text: str) -> str | None:
        return None if text.lower() in KEYS else _("type Enter, p, s or q")

    while True:
        answer = ui.ask("", check=valid).lower()
        if answer == "p":
            _play_all(ui, folder, samples, player)
        elif answer == "s":
            return Step.SKIP
        elif answer == "q":
            return Step.QUIT
        else:
            return Step.CONTINUE
