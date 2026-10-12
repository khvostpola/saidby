# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import inspect

import pytest

from saidby import cli, errors
from saidby.errors import ConsentMissingError, InputError, SaidbyError, UsageError


def _all_errors() -> list[type[SaidbyError]]:
    return [
        cls
        for _, cls in inspect.getmembers(errors, inspect.isclass)
        if issubclass(cls, SaidbyError)
    ]


def test_every_error_has_its_own_id_and_exit_code() -> None:
    classes = _all_errors()
    assert len(classes) == 8
    assert len({cls.error_id for cls in classes}) == len(classes)
    assert len({cls.exit_code for cls in classes}) == len(classes)


def test_ids_are_stable_lowercase_words() -> None:
    assert {cls.__name__: (cls.error_id, cls.exit_code) for cls in _all_errors()} == {
        "SaidbyError": ("error", 1),
        "UsageError": ("usage", 2),
        "InputError": ("input", 3),
        "ModelUnavailableError": ("model_unavailable", 4),
        "ConsentMissingError": ("consent_missing", 5),
        "StageError": ("stage_failed", 6),
        "LlmUnavailableError": ("llm_unavailable", 7),
        "NetworkAttemptError": ("network_attempt", 8),
    }


@pytest.mark.parametrize(
    ("error", "line", "code"),
    [
        (
            ConsentMissingError("no consent for ana"),
            "error: no consent for ana  [consent_missing · exit 5]",
            5,
        ),
        (InputError("file not found: x.m4a"), "error: file not found: x.m4a  [input · exit 3]", 3),
        (UsageError("unknown speaker 'x'"), "error: unknown speaker 'x'  [usage · exit 2]", 2),
    ],
)
def test_main_prints_the_message_then_the_id_and_the_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: SaidbyError,
    line: str,
    code: int,
) -> None:
    def fail() -> None:
        raise error

    monkeypatch.setattr(cli, "app", fail)
    with pytest.raises(SystemExit) as stop:
        cli.main()
    assert stop.value.code == code
    assert capsys.readouterr().err == line + "\n"


def test_interrupt_still_exits_130(monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupted() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "app", interrupted)
    with pytest.raises(SystemExit) as stop:
        cli.main()
    assert stop.value.code == 130
