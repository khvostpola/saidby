# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from pathlib import Path

from saidby.cli.ui import Ui
from saidby.errors import UsageError
from saidby.i18n import _, ngettext
from saidby.interactive.listen import clock
from saidby.schema.directory import Directory, Person
from saidby.schema.speakers import SpeakerEntry
from saidby.speakers import remap
from saidby.speakers.naming import ascii_slug, person_id_for
from saidby.speakers.people import add_person_to_file, find_person
from saidby.speakers.remap import Folder


@dataclass(frozen=True)
class Choice:
    entry: SpeakerEntry
    person: Person | None
    new_name: str | None

    @property
    def name(self) -> str:
        return self.person.name if self.person else str(self.new_name)


@dataclass(frozen=True)
class Naming:
    applied: list[tuple[str, str, str]]
    added: list[str]


class Namer:
    def __init__(
        self, ui: Ui, folder: Folder, merged: Directory | None, directory_files: list[Path]
    ) -> None:
        self.ui = ui
        self.folder = folder
        self.merged = merged
        self.files = directory_files
        self.chosen: dict[str, Choice] = {}

    def _find(self, text: str) -> Person | None:
        return find_person(self.merged, text) if self.merged and text else None

    def _options(self) -> list[str]:
        if self.merged is None:
            return []
        used = {c.person.id for c in self.chosen.values() if c.person}
        return [t for p in self.merged.people if p.id not in used for t in (p.id, p.name)]

    def _id_of(self, text: str) -> str:
        person = self._find(text)
        return person.id if person else ascii_slug(text)

    def _prospective_id(self, entry: SpeakerEntry) -> str:
        choice = self.chosen.get(entry.label)
        if choice is None:
            return entry.file_id
        return choice.person.id if choice.person else ascii_slug(choice.name)

    def _check(self, text: str, entry: SpeakerEntry) -> str | None:
        if not text:
            return None
        target = self._id_of(text)
        if not target:
            return _("use letters or digits in the name")
        for other in self.folder.transcript.speakers:
            if other.label != entry.label and self._prospective_id(other) == target:
                message = _(
                    "{who} is already {label}. Pick another name, or use "
                    '"saidby speakers merge" if the diarizer split one person.'
                )
                return message.format(who=text, label=other.label)
        return None

    def _intro(self) -> None:
        paint = self.ui.term.paint
        self.ui.say()
        self.ui.say(paint(_("Who is each voice?"), "bold"))
        self.ui.say(paint(_("Type an id or a name. Tab completes. Enter keeps the label."), "dim"))
        if self.merged and self.merged.people:
            people = " · ".join(f"{p.id} ({p.name})" for p in self.merged.people)
            self.ui.say(f"  {paint(_('directory:'), 'dim')} {people}")
        self.ui.say()

    def _ask(self, entry: SpeakerEntry) -> None:
        paint = self.ui.term.paint
        time = _("{time} of speech").format(time=clock(entry.speech_s))
        self.ui.say(f"{paint(entry.label, 'bold')}  {paint(time, 'dim')}")
        current = entry.display
        typed = self.ui.ask(
            _("Name or id?"),
            hint=_("[keep {current}]").format(current=current),
            check=lambda text: self._check(text, entry),
            complete=self._options,
        )
        if not typed:
            self.ui.say(f"  {paint('→', 'green')} {_('stays {current}').format(current=current)}")
            return
        person = self._find(typed)
        self.chosen[entry.label] = Choice(entry, person, None if person else typed)
        if person:
            self.ui.say(f"  {paint('→', 'green')} {person.name} {paint(f'({person.id})', 'dim')}")
        else:
            note = _("(new, will be added to the directory)") if self.files else _("(new name)")
            self.ui.say(f"  {paint('→', 'yellow')} {typed} {paint(note, 'dim')}")

    def _target_ids(self) -> dict[str, str]:
        taken = [s.file_id for s in self.folder.transcript.speakers if s.label not in self.chosen]
        taken += [c.person.id for c in self.chosen.values() if c.person]
        taken += [p.id for p in self.merged.people] if self.merged else []
        ids: dict[str, str] = {}
        for label, choice in self.chosen.items():
            ids[label] = choice.person.id if choice.person else person_id_for(choice.name, taken)
            taken.append(ids[label])
        return ids

    def _summary(self) -> None:
        self.ui.say()
        self.ui.say(self.ui.term.paint(_("Apply these names?"), "bold"))
        for label, new_id in self._target_ids().items():
            choice = self.chosen[label]
            change = f"speakers/{choice.entry.file_id}.flac → speakers/{new_id}.flac"
            self.ui.say(f"  {label:<12} → {choice.name:<14} {change}")

    def run(self) -> Naming | None:
        self._intro()
        for entry in self.folder.transcript.speakers:
            self._ask(entry)
        paint = self.ui.term.paint
        if not self.chosen:
            self.ui.say(f"  {paint(_('Nothing to rename.'), 'dim')}")
            return None
        self._summary()
        if not self.ui.confirm(_("Apply?"), default=True):
            self.ui.say(f"  {paint('→', 'yellow')} {_('nothing was changed')}")
            return None
        return self._apply()

    def _apply(self) -> Naming:
        paint = self.ui.term.paint
        applied: list[tuple[str, str, str]] = []
        added: list[str] = []
        ids = self._target_ids()
        kept = [s.file_id for s in self.folder.transcript.speakers if s.label not in self.chosen]
        if len({*kept, *ids.values()}) != len(kept) + len(ids):
            raise UsageError(_("two voices would end up with the same name; nothing was changed"))
        for label, choice in self.chosen.items():
            person = choice.person
            if person is None and self.files:
                person, backup = add_person_to_file(self.files[-1], choice.name, ids[label])
                added.append(person.name)
                extra = f" (backup: {backup})" if backup else ""
                where = f"{_('added to')} {self.files[-1]}{extra}"
                self.ui.say(f"  {paint('✓', 'green')} {person.name} {where}")
            remap.map_speaker(self.folder.out_dir, label, ids[label], choice.name)
            applied.append((label, ids[label], choice.name))
        done = ngettext("{n} track renamed", "{n} tracks renamed", len(applied))
        self.ui.say(f"  {paint('✓', 'green')} {done.format(n=len(applied))}")
        detail = _("rewrote the transcript files and the RTTM; no audio was re-processed")
        self.ui.say(paint(f"    {detail}", "dim"))
        return Naming(applied, added)


def name_speakers(
    ui: Ui, folder: Folder, merged: Directory | None, directory_files: list[Path]
) -> Naming | None:
    return Namer(ui, folder, merged, directory_files).run()
