# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from saidby.cli.progress import Progress
from saidby.cli.term import Terminal
from saidby.cli.ui import Ui
from saidby.config.settings import Settings
from saidby.engines.asr.fake import FakeTranscriber
from saidby.engines.diarize.fake import FakeDiarizer
from saidby.i18n import set_language
from saidby.interactive.plan import plan_run
from saidby.pipeline.runner import Pipeline

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/synthetic/tones_2spk_10s.flac"
RTTM = ROOT / "fixtures/synthetic/tones_2spk_10s.rttm"
PLAIN = Terminal(tty=True, color=False, truecolor=False, columns=100)
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _saidby(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base = {k: v for k, v in os.environ.items() if not k.startswith(("SAIDBY_", "LC_", "LANG"))}
    return subprocess.run(
        ["saidby", *args],
        capture_output=True,
        text=True,
        check=False,
        env={**base, **(env or {})},
        encoding="utf-8",
    )


def test_an_error_is_written_in_spanish_but_keeps_its_english_id_and_code(tmp_path: Path) -> None:
    result = _saidby("--ui-lang", "es", "directory", "validate", str(tmp_path / "nope.yaml"))
    assert result.returncode == 3
    assert "error: no se encontró el archivo de directorio:" in result.stderr
    assert "[input · exit 3]" in result.stderr


def test_the_system_locale_picks_the_language_and_an_option_beats_it(tmp_path: Path) -> None:
    missing = str(tmp_path / "nope.yaml")
    locale = {"LANG": "es_CO.UTF-8"}
    spanish = _saidby("directory", "validate", missing, env=locale)
    assert "no se encontró el archivo de directorio" in spanish.stderr
    english = _saidby("--ui-lang", "en", "directory", "validate", missing, env=locale)
    assert "directory file not found" in english.stderr


def test_a_language_without_a_catalog_falls_back_to_english(tmp_path: Path) -> None:
    result = _saidby("--ui-lang", "fr", "directory", "validate", str(tmp_path / "nope.yaml"))
    assert "directory file not found" in result.stderr


def test_doctor_json_stays_in_english_whatever_the_language() -> None:
    result = _saidby("--ui-lang", "es", "doctor", "--json")
    details = {c["name"]: c["detail"] for c in json.loads(result.stdout)["checks"]}
    assert details["offline"].startswith("processing always runs offline")


@needs_ffmpeg
def test_progress_lines_are_written_in_spanish(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    set_language("es")
    pipeline = Pipeline(
        Settings(device="cpu", language="es"),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("human"),
    )
    pipeline.run([FIXTURE], tmp_path)
    lines = capsys.readouterr().err.strip().splitlines()
    text = "\n".join(lines)
    assert "de audio" in text
    assert "transcripción" in text
    assert "2 hablantes" in text
    assert lines[-1].startswith("[total]")
    assert "inicio " in lines[-1]
    assert "fin " in lines[-1]
    assert "x más rápido que el audio" in lines[-1] or "x más lento que el audio" in lines[-1]


def test_the_plan_screen_and_yes_no_answers_work_in_spanish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    set_language("es")
    feed = iter(["", ""])
    out = io.StringIO()
    ui = Ui(PLAIN, input_fn=lambda prompt: next(feed), out=out)
    plan = plan_run(ui, [Path("llamada.m4a")], Settings(language="es"))
    assert plan is not None
    text = out.getvalue()
    assert "Listo para procesar 1 archivo" in text
    assert "glosario" in text
    assert "Enter empezar" in text
    answers = iter(["s", "N"])
    ask = Ui(PLAIN, input_fn=lambda prompt: next(answers), out=io.StringIO())
    assert ask.confirm("¿Seguir?", default=False) is True
    assert ask.confirm("¿Seguir?", default=True) is False


@needs_ffmpeg
def test_failures_are_recorded_in_english_even_when_shown_in_spanish(tmp_path: Path) -> None:
    set_language("es")
    pipeline = Pipeline(
        Settings(device="cpu", language="es"),
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("none"),
    )
    missing = tmp_path / "nope.m4a"
    result = pipeline.run([missing], tmp_path / "out")[0]
    assert result.status == "failed"
    manifest = json.loads((result.out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["error"] == f"input file not found: {missing}"
    log = (result.out_dir / "logs" / "run.log").read_text(encoding="utf-8")
    assert f"InputError: input file not found: {missing}" in log
    assert "no se encontró" not in log
