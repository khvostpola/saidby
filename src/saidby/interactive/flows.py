# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from saidby.cli.ui import Ui
from saidby.formats.directory_set import load_directory_set
from saidby.i18n import _
from saidby.interactive.listen import Player, Step, listen
from saidby.interactive.name import Naming, name_speakers
from saidby.runtime.procs import play
from saidby.speakers.remap import Folder


def name_voices(
    ui: Ui, out_dir: Path, directory_files: list[Path], *, title: str, player: Player = play
) -> Naming | None:
    folder = Folder(out_dir)
    step = listen(ui, folder, title=title, player=player)
    if step is Step.QUIT:
        ui.say(f"  {ui.term.paint('→', 'yellow')} {_('stopped; the files are as they were')}")
        return None
    if step is Step.SKIP:
        ui.say(
            f"  {ui.term.paint('→', 'yellow')} {_('naming skipped; the labels stay as they are')}"
        )
        return None
    merged = load_directory_set(directory_files).merged if directory_files else None
    return name_speakers(ui, folder, merged, directory_files)
