# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import shlex
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from saidby.cli.next_steps import FolderState, next_steps, read_state
from saidby.cli.paths import show_path
from saidby.cli.ui import Ui
from saidby.config.settings import Settings
from saidby.config.writer import update_config
from saidby.formats.directory_set import consent_path
from saidby.formats.manifest import read_manifest, write_manifest
from saidby.i18n import _, ngettext
from saidby.interactive.flows import name_voices
from saidby.interactive.plan import RunPlan
from saidby.interactive.save import (
    DIRECTORY_NAME,
    add_terms_to_directory,
    config_target,
    create_directory_with_terms,
    path_for_config,
)
from saidby.interactive.voices import store_voices
from saidby.pipeline.job import RecordingResult
from saidby.schema.manifest import DeviceRecord
from saidby.speakers.enrollment import DEFAULT_CHANNEL


@dataclass
class FolderOutcome:
    out_dir: Path
    renamed: int = 0
    added_people: list[str] = field(default_factory=list)
    voiceprints: int = 0
    doubtful: int = 0


@dataclass
class Finish:
    terms_saved: list[str] = field(default_factory=list)
    terms_file: Path | None = None
    settings_file: Path | None = None
    settings_saved: dict[str, str] = field(default_factory=dict)


def device_text(record: DeviceRecord) -> str:
    if record.used == "cuda":
        gb = f"{round(record.vram_total_mb / 1024)} GB" if record.vram_total_mb else ""
        return " · ".join(p for p in ("GPU", "cuda", record.name or "", gb) if p)
    return "CPU" + (f" ({record.reason.replace('_', ' ')})" if record.reason else "")


def record_interactive(out_dir: Path, outcome: FolderOutcome) -> None:
    if not (outcome.renamed or outcome.voiceprints):
        return
    path = out_dir / "manifest.json"
    manifest = read_manifest(path)
    entry = {
        "at": datetime.now(UTC).isoformat(),
        "op": "interactive",
        "renamed": outcome.renamed,
        "voiceprints": outcome.voiceprints,
    }
    write_manifest(path, manifest.model_copy(update={"edits": [*manifest.edits, entry]}))


class Walk:
    def __init__(self, ui: Ui, settings: Settings) -> None:
        self.ui = ui
        self.settings = settings

    def _voiceprints(self, out_dir: Path) -> int:
        files = self.settings.directory
        if not files:
            return 0
        question = _("Store voiceprints so saidby recognizes these voices next time?")
        if not self.ui.confirm(question, default=False):
            return 0
        enrolled = store_voices(
            self.ui,
            out_dir,
            files[-1],
            consent_path(files[-1]),
            embedder_name=self.settings.embedder,
            device=self.settings.device,
            channel=DEFAULT_CHANNEL,
        )
        return len(enrolled.stored) if enrolled else 0

    def folder(self, result: RecordingResult, index: int, total: int) -> FolderOutcome:
        outcome = FolderOutcome(result.out_dir)
        state = read_state(result.out_dir)
        title = _("Voices in {folder}").format(folder=show_path(result.out_dir))
        if total > 1:
            title += " " + _("({index} of {total})").format(index=index, total=total)
        if state is not None and state.unnamed:
            naming = name_voices(self.ui, result.out_dir, self.settings.directory, title=title)
            if naming is not None:
                outcome.renamed = len(naming.applied)
                outcome.added_people = naming.added
        else:
            note = _("Every voice in {folder} already has a name.")
            self.ui.say()
            self.ui.say(self.ui.term.paint(note.format(folder=show_path(result.out_dir)), "dim"))
        if outcome.renamed:
            outcome.voiceprints = self._voiceprints(result.out_dir)
        after = read_state(result.out_dir)
        outcome.doubtful = after.doubtful if after else 0
        record_interactive(result.out_dir, outcome)
        return outcome


def walk_folders(ui: Ui, results: list[RecordingResult], settings: Settings) -> list[FolderOutcome]:
    walk = Walk(ui, settings)
    ok = [r for r in results if r.status == "ok"]
    return [walk.folder(r, i, len(ok)) for i, r in enumerate(ok, start=1)]


def _offer_terms(ui: Ui, plan: RunPlan, config_file: Path, finish: Finish) -> None:
    terms = plan.added_terms
    if not terms:
        return
    count = len(terms)
    files = plan.settings.directory
    if files:
        question = ngettext(
            "Save the {n} term from this run to {path}?",
            "Save the {n} terms from this run to {path}?",
            count,
        ).format(n=count, path=show_path(files[-1]))
        if ui.confirm(question, default=False):
            saved, backup = add_terms_to_directory(files[-1], terms)
            finish.terms_saved, finish.terms_file = saved, files[-1]
            if backup:
                ui.say(ui.term.paint(f"    {_('backup:')} {backup}", "dim"))
        return
    target = config_file.parent / DIRECTORY_NAME
    question = _("Keep these terms in a new glossary, {path}?").format(path=show_path(target))
    if target.exists() or not ui.confirm(question, default=False):
        return
    finish.terms_saved = create_directory_with_terms(target, plan.settings.language, terms)
    finish.terms_file = target
    plan.chosen["directory"] = str(target)


def _offer_settings(ui: Ui, plan: RunPlan, config_file: Path, finish: Finish) -> None:
    settings = plan.settings
    wanted: dict[str, str] = {}
    if "language" in plan.chosen and settings.language:
        wanted["language"] = settings.language
    if "out" in plan.chosen:
        wanted["out"] = path_for_config(settings.out, config_file)
    if "directory" in plan.chosen:
        files = [Path(plan.chosen["directory"])] if plan.chosen["directory"] else []
        wanted["directory"] = ", ".join(path_for_config(p, config_file) for p in files) or "none"
    if not wanted:
        return
    what = ", ".join(f"{key} {value}" for key, value in wanted.items())
    question = _("Save {what} to {path} so you do not have to say it again?").format(
        what=what, path=show_path(config_file)
    )
    if not ui.confirm(question, default=True):
        return
    directory = None
    if "directory" in plan.chosen:
        files = [Path(plan.chosen["directory"])] if plan.chosen["directory"] else []
        directory = [path_for_config(p, config_file) for p in files]
    backup = update_config(
        config_file,
        language=wanted.get("language"),
        out=wanted.get("out"),
        directory=directory,
    )
    finish.settings_file, finish.settings_saved = config_file, wanted
    if backup:
        ui.say(ui.term.paint(f"    {_('backup:')} {backup}", "dim"))


def equivalent_command(inputs: list[Path], plan: RunPlan, finish: Finish) -> str:
    settings = plan.settings
    parts = ["saidby", "process", *(shlex.quote(str(p)) for p in inputs)]
    if "language" in plan.chosen and "language" not in finish.settings_saved and settings.language:
        parts += ["--language", settings.language]
    if "directory" in plan.chosen and "directory" not in finish.settings_saved:
        parts += [f"--directory {shlex.quote(str(f))}" for f in settings.directory]
    if "out" in plan.chosen and "out" not in finish.settings_saved:
        parts += ["--out", shlex.quote(str(settings.out))]
    if "num_speakers" in plan.chosen and settings.num_speakers:
        parts += ["--num-speakers", str(settings.num_speakers)]
    unsaved = [t for t in plan.added_terms if t not in finish.terms_saved]
    parts += [f"--term {shlex.quote(t)}" for t in unsaved]
    return " ".join(parts)


def _device_of(results: list[RecordingResult]) -> str | None:
    for result in results:
        if result.status == "ok":
            return device_text(read_manifest(result.out_dir / "manifest.json").device)
    return None


def _outcome_line(outcome: FolderOutcome) -> str:
    parts: list[str] = []
    if outcome.renamed:
        parts.append(
            ngettext("{n} voice named", "{n} voices named", outcome.renamed).format(
                n=outcome.renamed
            )
        )
    if outcome.added_people:
        parts.append(
            ngettext(
                "{n} person added to the directory",
                "{n} people added to the directory",
                len(outcome.added_people),
            ).format(n=len(outcome.added_people))
        )
    if outcome.voiceprints:
        parts.append(
            ngettext("{n} voiceprint stored", "{n} voiceprints stored", outcome.voiceprints).format(
                n=outcome.voiceprints
            )
        )
    if outcome.doubtful:
        parts.append(
            ngettext("{n} doubtful span", "{n} doubtful spans", outcome.doubtful).format(
                n=outcome.doubtful
            )
        )
    return " · ".join(parts) or _("nothing changed")


def finish_run(
    ui: Ui,
    inputs: list[Path],
    results: list[RecordingResult],
    plan: RunPlan,
    outcomes: list[FolderOutcome],
    config: Path | None,
) -> None:
    if not any(r.status == "ok" for r in results):
        return
    paint = ui.term.paint
    config_file = config_target(config)
    finish = Finish()
    ui.say()
    _offer_terms(ui, plan, config_file, finish)
    _offer_settings(ui, plan, config_file, finish)
    ui.say()
    ui.say(paint(_("Summary"), "bold"))
    device = _device_of(results)
    if device:
        ui.say(f"  {paint(_('device').ljust(10), 'bold')}{device}")
    for outcome in outcomes:
        name = outcome.out_dir.name
        label = name.ljust(10) if len(name) < 10 else f"{name}  "
        ui.say(f"  {paint(label, 'bold')}{_outcome_line(outcome)}")
    if finish.terms_saved:
        count = len(finish.terms_saved)
        saved = ngettext("{n} term saved to {path}", "{n} terms saved to {path}", count)
        ui.say(
            f"  {paint(_('glossary').ljust(10), 'bold')}"
            f"{saved.format(n=count, path=show_path(finish.terms_file or Path()))}"
        )
    if finish.settings_file:
        saved_to = _("saved to {path}").format(path=show_path(finish.settings_file))
        ui.say(f"  {paint(_('settings').ljust(10), 'bold')}{saved_to}")
    states: list[FolderState] = []
    for outcome in outcomes:
        state = read_state(outcome.out_dir)
        if state is not None:
            states.append(state)
    for line in next_steps(states, ui.term):
        ui.say(line)
    ui.say(f"  {paint(_('again').ljust(10), 'bold')}{equivalent_command(inputs, plan, finish)}")
