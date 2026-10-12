# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from pathlib import Path

from saidby.cli.ui import Ui
from saidby.formats.consent_yaml import find_consent, load_consents
from saidby.formats.directory_yaml import load_directory
from saidby.i18n import _, ngettext
from saidby.interactive.listen import clock
from saidby.runtime import host
from saidby.schema.directory import ConsentRecord, Person
from saidby.schema.speakers import SpeakerEntry
from saidby.speakers.enrollment import (
    ConsentInput,
    enroll_voices,
    ensure_audio,
    prepare_consents,
)
from saidby.speakers.people import find_person
from saidby.speakers.remap import Folder


@dataclass(frozen=True)
class VoiceChoice:
    label: str
    person: Person
    given: ConsentInput | None


@dataclass(frozen=True)
class Enrolled:
    stored: list[str]
    declined: list[str]
    backup: Path | None


def _on_record(record: ConsentRecord) -> str:
    declared = _("declared by {who}").format(who=record.declared_by)
    return f"{record.source}, {declared}, {record.date}"


class Voices:
    def __init__(self, ui: Ui, folder: Folder, target: Path, consent_file: Path) -> None:
        self.ui = ui
        self.folder = folder
        self.target = target
        self.consent_file = consent_file
        self.model, _raw = load_directory(target)
        self.records, _records_raw = load_consents(consent_file)
        self.source: str | None = None
        self.declined: list[str] = []

    def _person_of(self, entry: SpeakerEntry) -> Person | None:
        for key in (entry.id, entry.name):
            person = find_person(self.model, key) if key else None
            if person is not None:
                return person
        return None

    def _sort(self) -> tuple[list[tuple[SpeakerEntry, Person]], list[str], list[str]]:
        found: list[tuple[SpeakerEntry, Person]] = []
        unnamed: list[str] = []
        elsewhere: list[str] = []
        for entry in self.folder.transcript.speakers:
            person = self._person_of(entry)
            if person is not None:
                found.append((entry, person))
            elif entry.name or entry.id:
                elsewhere.append(entry.display)
            else:
                unnamed.append(entry.label)
        return found, unnamed, elsewhere

    def _intro(self) -> None:
        paint = self.ui.term.paint
        self.ui.say()
        self.ui.say(paint(_("Voiceprints"), "bold"))
        for line in (
            _("A voiceprint is a numeric summary of a voice. saidby uses it to recognize"),
            _("the person in future recordings. It is personal data: store it only with"),
            _("the person's consent."),
        ):
            self.ui.say(paint(f"  {line}", "dim"))
        self.ui.say()

    def _consent_for(self, person: Person) -> ConsentInput:
        if self.source is None:
            self.source = self.ui.ask(
                _("How was consent given?"),
                hint=_("[for example: signed form]"),
                check=lambda text: None if text else _("this cannot be empty"),
            )
        else:
            note = _("consent given by: {source}").format(source=self.source)
            self.ui.say(self.ui.term.paint(f"  {note}", "dim"))
        declared = self.ui.ask(_("Declared by?"), default=person.name, hint=f"[{person.name}]")
        return ConsentInput(self.source, declared)

    def _decide(self, entry: SpeakerEntry, person: Person) -> VoiceChoice | None:
        paint = self.ui.term.paint
        time = _("{time} of speech").format(time=clock(entry.speech_s))
        self.ui.say(f"{paint(person.name, 'bold')}  {paint(f'{entry.label} · {time}', 'dim')}")
        if person.voiceprint:
            self.ui.say(paint(f"  {_('already has a voiceprint')}", "dim"))
        record = find_consent(self.records, person.id, person.name)
        if record is not None:
            self.ui.say(paint(f"  {_('consent on record:')} {_on_record(record)}", "dim"))
            question = _("Replace the voiceprint?") if person.voiceprint else _("Store it?")
            if self.ui.confirm(question, default=not person.voiceprint):
                return VoiceChoice(entry.label, person, None)
            self.ui.say(f"  {paint('→', 'yellow')} {_('left as it was')}")
            return None
        asked = _("Did {name} agree to have their voiceprint stored?").format(name=person.name)
        if not self.ui.confirm(asked, default=False):
            self.declined.append(person.name)
            self.ui.say(f"  {paint('→', 'yellow')} {_('no consent, so no voiceprint')}")
            return None
        return VoiceChoice(entry.label, person, self._consent_for(person))

    def _summary(self, chosen: list[VoiceChoice]) -> None:
        paint = self.ui.term.paint
        self.ui.say()
        self.ui.say(paint(_("Store these voiceprints?"), "bold"))
        for choice in chosen:
            if choice.given is None:
                why = _("consent on record")
            else:
                declared = _("declared by {who}").format(who=choice.given.declared_by)
                why = f"{choice.given.source}, {declared}"
            self.ui.say(f"  {choice.person.name:<16} {choice.label:<12} {paint(why, 'dim')}")
        where = _("in {path}").format(path=self.target)
        self.ui.say(paint(f"  {where}", "dim"))

    def run(self, *, embedder_name: str, device: str, channel: str) -> Enrolled | None:
        paint = self.ui.term.paint
        found, unnamed, elsewhere = self._sort()
        self._intro()
        if unnamed:
            command = f"saidby speakers map -i {host.quote(str(self.folder.out_dir))}"
            note = _("{labels} have no name yet; run {command} first").format(
                labels=", ".join(unnamed), command=command
            )
            self.ui.say(paint(f"  {note}", "dim"))
        if elsewhere:
            note = _("{names} are not in {path}; pass --directory with the file that has them")
            note = note.format(names=", ".join(elsewhere), path=self.target)
            self.ui.say(paint(f"  {note}", "dim"))
        if not found:
            self.ui.say(f"  {paint('→', 'yellow')} {_('no named voice to store')}")
            return None
        chosen = [c for entry, person in found if (c := self._decide(entry, person))]
        if not chosen:
            self.ui.say(f"  {paint('→', 'yellow')} {_('no voiceprint was stored')}")
            return None
        self._summary(chosen)
        if not self.ui.confirm(_("Store?"), default=True):
            self.ui.say(f"  {paint('→', 'yellow')} {_('nothing was stored')}")
            return None
        return self._store(chosen, embedder_name, device, channel)

    def _store(
        self, chosen: list[VoiceChoice], embedder_name: str, device: str, channel: str
    ) -> Enrolled:
        paint = self.ui.term.paint
        self.ui.say(paint(f"  {_('computing voiceprints...')}", "dim"))
        ensure_audio(self.folder.out_dir)
        pending = prepare_consents(
            [c.person for c in chosen],
            self.consent_file,
            {c.person.id: c.given for c in chosen if c.given},
        )
        _model, raw = load_directory(self.target)
        backup = enroll_voices(
            self.folder.out_dir,
            [(c.label, c.person.id) for c in chosen],
            self.target,
            raw,
            pending,
            self.consent_file,
            embedder_name=embedder_name,
            device=device,
            channel=channel,
            echo=lambda line: self.ui.say(f"  {line}"),
        )
        stored = ngettext("{n} voiceprint stored", "{n} voiceprints stored", len(chosen))
        self.ui.say(f"  {paint('✓', 'green')} {stored.format(n=len(chosen))}")
        if backup:
            self.ui.say(paint(f"    {_('backup:')} {backup}", "dim"))
        return Enrolled([c.person.id for c in chosen], self.declined, backup)


def store_voices(
    ui: Ui,
    out_dir: Path,
    directory_file: Path,
    consent_file: Path,
    *,
    embedder_name: str,
    device: str,
    channel: str,
) -> Enrolled | None:
    voices = Voices(ui, Folder(out_dir), directory_file, consent_file)
    return voices.run(embedder_name=embedder_name, device=device, channel=channel)
