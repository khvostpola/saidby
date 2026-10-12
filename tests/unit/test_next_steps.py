# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from saidby.cli.next_steps import FolderState, next_steps
from saidby.cli.term import Terminal

PLAIN = Terminal(tty=False, color=False, truecolor=False, columns=80)
COLOR = Terminal(tty=True, color=True, truecolor=False, columns=80)


def _state(
    name: str = "saidby/call", unnamed: tuple[str, ...] = (), doubtful: int = 0
) -> FolderState:
    return FolderState(Path(name), unnamed, doubtful)


def test_nothing_to_do_means_no_footer() -> None:
    assert next_steps([_state()], PLAIN) == []
    assert next_steps([], PLAIN) == []


def test_unnamed_speakers_point_to_speakers_map() -> None:
    lines = next_steps([_state(unnamed=("SPEAKER_00", "SPEAKER_01"))], PLAIN)
    assert lines == ["  name:     saidby speakers map -i saidby/call"]


def test_doubtful_spans_point_to_review_with_the_count() -> None:
    lines = next_steps([_state(doubtful=3)], PLAIN)
    assert lines == ["  review:   saidby review saidby/call   3 doubtful spans"]
    assert next_steps([_state(doubtful=1)], PLAIN)[0].endswith("1 doubtful span")


def test_both_show_up_in_that_order() -> None:
    lines = next_steps([_state(unnamed=("SPEAKER_00",), doubtful=2)], PLAIN)
    assert [line.split()[0] for line in lines] == ["name:", "review:"]


def test_several_folders_name_the_first_and_count_them_all() -> None:
    states = [
        _state("saidby/a", unnamed=("SPEAKER_01",), doubtful=2),
        _state("saidby/b"),
        _state("saidby/c", unnamed=("SPEAKER_00",), doubtful=5),
    ]
    lines = next_steps(states, PLAIN)
    assert lines[0] == (
        "  name:     saidby speakers map -i saidby/a   2 folders have speakers without names"
    )
    assert lines[1] == "  review:   saidby review saidby/a   7 doubtful spans"


def test_paths_with_spaces_are_quoted() -> None:
    lines = next_steps([_state("my results/call 1", unnamed=("SPEAKER_00",))], PLAIN)
    assert "saidby speakers map -i 'my results/call 1'" in lines[0]


def test_color_goes_on_the_label_and_the_command_only() -> None:
    line = next_steps([_state(doubtful=2)], COLOR)[0]
    assert line.startswith("  \x1b[2mreview:  \x1b[0m ")
    assert "\x1b[36msaidby review saidby/call\x1b[0m" in line
