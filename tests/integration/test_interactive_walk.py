# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import io
import sys
import tomllib
from pathlib import Path
from typing import Any, ClassVar

import pytest
import yaml
from typer.testing import CliRunner

from saidby.cli import app
from saidby.cli.progress import Progress
from saidby.cli.term import Terminal
from saidby.cli.ui import Ui
from saidby.config.settings import Settings
from saidby.engines.asr.fake import FakeTranscriber
from saidby.engines.diarize.fake import FakeDiarizer
from saidby.formats.manifest import read_manifest
from saidby.formats.words_json import read_transcript
from saidby.interactive.plan import RunPlan
from saidby.interactive.walk import Finish, equivalent_command, finish_run, walk_folders
from saidby.pipeline.job import RecordingResult
from saidby.pipeline.runner import Pipeline

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/synthetic/tones_2spk_10s.flac"
RTTM = ROOT / "fixtures/synthetic/tones_2spk_10s.rttm"
PLAIN = Terminal(tty=True, color=False, truecolor=False, columns=100)
runner = CliRunner()

pytestmark = pytest.mark.needs_ffmpeg


def _settings(directory: Path | None, **extra: Any) -> Settings:
    return Settings(
        device="cpu",
        language="es",
        embedder="fake",
        directory=[directory] if directory else [],
        **extra,
    )


def _run(tmp_path: Path, settings: Settings, count: int = 1) -> list[RecordingResult]:
    pipeline = Pipeline(
        settings,
        transcriber=FakeTranscriber(),
        diarizer=FakeDiarizer(rttm=RTTM),
        progress=Progress("none"),
    )
    results = pipeline.run([FIXTURE] * count, tmp_path / "out")
    assert all(r.status == "ok" for r in results)
    return results


def _directory(tmp_path: Path) -> Path:
    path = tmp_path / "directory.yaml"
    path.write_text(
        "version: 1\nlanguage: es\npeople:\n  - id: ana\n    name: Ana\n"
        "  - id: ben\n    name: Ben\nterms:\n  - term: Acme\n",
        encoding="utf-8",
    )
    return path


def _session(answers: list[str]) -> tuple[Ui, io.StringIO, list[str]]:
    feed = iter(answers)
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(feed)

    out = io.StringIO()
    return Ui(PLAIN, input_fn=fake_input, out=out), out, prompts


@pytest.fixture
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_each_folder_is_listened_to_named_and_recorded(work: Path) -> None:
    directory = _directory(work)
    settings = _settings(directory)
    results = _run(work, settings)
    ui, out, prompts = _session(["", "ana", "ben", "", "n"])
    outcomes = walk_folders(ui, results, settings)
    assert [(o.renamed, o.voiceprints) for o in outcomes] == [(2, 0)]
    transcript = read_transcript(results[0].out_dir / "transcript.words.json")
    assert [s.name for s in transcript.speakers] == ["Ana", "Ben"]
    assert any("Store voiceprints" in p for p in prompts)
    edits = read_manifest(results[0].out_dir / "manifest.json").edits
    assert edits[-1]["op"] == "interactive"
    assert (edits[-1]["renamed"], edits[-1]["voiceprints"]) == (2, 0)
    assert "Voices in" in out.getvalue()


def test_voiceprints_are_stored_with_consent_when_asked(work: Path) -> None:
    directory = _directory(work)
    settings = _settings(directory)
    results = _run(work, settings)
    answers = ["", "ana", "ben", "", "y", "y", "signed form", "", "y", "", ""]
    ui, out, _ = _session(answers)
    outcomes = walk_folders(ui, results, settings)
    assert outcomes[0].voiceprints == 2
    saved = yaml.safe_load(directory.read_text(encoding="utf-8"))
    assert all("voiceprint" in p for p in saved["people"])
    assert len(yaml.safe_load((work / "consent.yaml").read_text(encoding="utf-8"))) == 2
    assert "2 voiceprints stored" in out.getvalue()
    assert read_manifest(results[0].out_dir / "manifest.json").edits[-1]["voiceprints"] == 2


def test_without_a_directory_voiceprints_are_not_offered(work: Path) -> None:
    settings = _settings(None)
    results = _run(work, settings)
    ui, _, prompts = _session(["", "Ana Díaz", "", ""])
    outcomes = walk_folders(ui, results, settings)
    assert outcomes[0].renamed == 1
    assert not any("Store voiceprints" in p for p in prompts)


def test_a_folder_whose_voices_are_all_named_is_not_asked_about(work: Path) -> None:
    settings = _settings(None)
    results = _run(work, settings)
    ui, _, _ = _session(["", "Ana", "Ben", ""])
    walk_folders(ui, results, settings)
    quiet, out, prompts = _session([])
    outcomes = walk_folders(quiet, results, settings)
    assert prompts == []
    assert outcomes[0].renamed == 0
    assert "already has a name" in out.getvalue()


def test_several_folders_are_walked_in_order_and_failures_are_skipped(work: Path) -> None:
    settings = _settings(None)
    results = _run(work, settings, count=2)
    failed = RecordingResult("gone", work / "out" / "gone", "failed", 4)
    ui, out, _ = _session(["s", "s"])
    outcomes = walk_folders(ui, [results[0], failed, results[1]], settings)
    assert len(outcomes) == 2
    assert "(1 of 2)" in out.getvalue()
    assert "(2 of 2)" in out.getvalue()


def _plan(settings: Settings, terms: list[str], chosen: dict[str, str]) -> RunPlan:
    return RunPlan(settings.model_copy(update={"terms": terms}), terms, chosen)


def test_run_terms_are_saved_to_the_glossary_only_when_asked(work: Path) -> None:
    directory = _directory(work)
    settings = _settings(directory)
    results = _run(work, settings)
    plan = _plan(settings, ["Acme", "Zeta"], {})
    ui, out, _ = _session(["n"])
    finish_run(ui, [FIXTURE], results, plan, [], None)
    assert "Zeta" not in directory.read_text(encoding="utf-8")
    ui, out, _ = _session(["y"])
    finish_run(ui, [FIXTURE], results, plan, [], None)
    terms = [t["term"] for t in yaml.safe_load(directory.read_text(encoding="utf-8"))["terms"]]
    assert terms == ["Acme", "Zeta"]
    assert list(work.glob("directory.bak-*.yaml"))
    assert "1 term saved to" in out.getvalue()


def test_without_a_glossary_the_terms_can_start_one_and_register_it(work: Path) -> None:
    settings = _settings(None)
    results = _run(work, settings)
    plan = _plan(settings, ["Acme"], {})
    ui, out, prompts = _session(["y", "y"])
    finish_run(ui, [FIXTURE], results, plan, [], None)
    assert [
        t["term"]
        for t in yaml.safe_load((work / "directory.yaml").read_text(encoding="utf-8"))["terms"]
    ] == ["Acme"]
    assert tomllib.loads((work / "saidby.toml").read_text(encoding="utf-8")) == {
        "glossary": {"directory": ["directory.yaml"]}
    }
    assert any("new glossary" in p for p in prompts)
    assert "settings" in out.getvalue()


def test_chosen_defaults_are_saved_into_the_project_file(work: Path) -> None:
    (work / "saidby.toml").write_text('# mine\n[saidby]\ndevice = "cpu"\n', encoding="utf-8")
    settings = _settings(None, out=Path("results"))
    results = _run(work, settings)
    chosen = {"language": "es", "out": "results"}
    ui, out, _ = _session([""])
    finish_run(ui, [FIXTURE], results, _plan(settings, [], chosen), [], None)
    text = (work / "saidby.toml").read_text(encoding="utf-8")
    assert text.startswith("# mine")
    assert tomllib.loads(text) == {"saidby": {"device": "cpu", "language": "es", "out": "results"}}
    assert "settings  saved to ./saidby.toml" in out.getvalue()


def test_declining_the_defaults_writes_nothing(work: Path) -> None:
    settings = _settings(None)
    results = _run(work, settings)
    ui, _, _ = _session(["n"])
    finish_run(ui, [FIXTURE], results, _plan(settings, [], {"language": "es"}), [], None)
    assert not (work / "saidby.toml").exists()


def test_nothing_chosen_and_no_terms_asks_nothing_and_still_summarizes(work: Path) -> None:
    settings = _settings(None)
    results = _run(work, settings)
    ui, out, prompts = _session([])
    finish_run(ui, [FIXTURE], results, _plan(settings, [], {}), [], None)
    assert prompts == []
    text = out.getvalue()
    assert "Summary" in text
    assert "device    CPU (requested cpu)" in text
    assert "saidby process" in text


def test_the_equivalent_command_carries_only_what_was_not_saved() -> None:
    settings = Settings(language="pt", directory=[Path("my dir.yaml")], out=Path("results"))
    plan = RunPlan(
        settings.model_copy(update={"num_speakers": 2}),
        ["Acme", "Rappi Pay"],
        {"language": "pt", "directory": "my dir.yaml", "out": "results", "num_speakers": "2"},
    )
    bare = equivalent_command([Path("call.m4a")], plan, Finish())
    assert bare == (
        "saidby process call.m4a --language pt --directory 'my dir.yaml' --out results "
        "--num-speakers 2 --term Acme --term 'Rappi Pay'"
    )
    saved = Finish(
        terms_saved=["Acme"], settings_saved={"language": "pt", "directory": "x", "out": "results"}
    )
    assert equivalent_command([Path("call.m4a")], plan, saved) == (
        "saidby process call.m4a --num-speakers 2 --term 'Rappi Pay'"
    )


class FakePipeline:
    results: ClassVar[list[RecordingResult]] = []

    def __init__(self, settings: Settings, **_: Any) -> None:
        self.settings = settings

    def run(self, inputs: list[Path], out_root: Path) -> list[RecordingResult]:
        return FakePipeline.results


def test_the_command_walks_the_folders_after_the_run(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(None)
    FakePipeline.results = _run(work, settings)
    ui, out, _ = _session(["es", "", "", "Ana", "Ben", "", "n"])
    module = sys.modules["saidby.cli.process"]
    monkeypatch.setattr(module, "ensure_terminal", lambda command: None)
    monkeypatch.setattr(module, "_ui", lambda: ui)
    monkeypatch.setattr(module, "Pipeline", FakePipeline)
    result = runner.invoke(app, ["process", str(FIXTURE), "-i"])
    assert result.exit_code == 0, result.output
    words = FakePipeline.results[0].out_dir / "transcript.words.json"
    names = [s.name for s in read_transcript(words).speakers]
    assert names == ["Ana", "Ben"]
    assert "Summary" in out.getvalue()
    assert not (work / "saidby.toml").exists()


def test_a_failed_input_still_sets_the_exit_code_after_the_walk(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(None)
    good = _run(work, settings)
    FakePipeline.results = [*good, RecordingResult("bad", work / "out" / "bad", "failed", 4)]
    ui, _, _ = _session(["es", "", "s", "n"])
    module = sys.modules["saidby.cli.process"]
    monkeypatch.setattr(module, "ensure_terminal", lambda command: None)
    monkeypatch.setattr(module, "_ui", lambda: ui)
    monkeypatch.setattr(module, "Pipeline", FakePipeline)
    result = runner.invoke(app, ["process", str(FIXTURE), "-i"])
    assert result.exit_code == 4


def test_a_failure_while_storing_voiceprints_does_not_end_the_walk(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from saidby.errors import InputError

    directory = _directory(work)
    settings = _settings(directory)
    results = _run(work, settings)

    def broken(*args: Any, **kwargs: Any) -> None:
        raise InputError("original recording not found: x")

    monkeypatch.setattr("saidby.interactive.walk.store_voices", broken)
    ui, out, _ = _session(["", "ana", "ben", "", "y"])
    outcomes = walk_folders(ui, results, settings)
    assert outcomes[0].renamed == 2
    assert outcomes[0].voiceprints == 0
    assert "original recording not found: x" in out.getvalue()
    assert "no voiceprint was stored" in out.getvalue()


def test_a_dropped_glossary_is_saved_or_flagged_as_for_this_run_only(work: Path) -> None:
    (work / "saidby.toml").write_text(
        '[glossary]\ndirectory = ["directory.yaml"]\n', encoding="utf-8"
    )
    settings = _settings(None)
    results = _run(work, settings)
    plan = _plan(settings, [], {"directory": ""})
    ui, out, _ = _session(["n"])
    finish_run(ui, [FIXTURE], results, plan, [], None)
    assert "none for this run only; the next run uses the configured one" in out.getvalue()
    assert "directory" in (work / "saidby.toml").read_text(encoding="utf-8")
    ui, out, _ = _session([""])
    finish_run(ui, [FIXTURE], results, plan, [], None)
    assert (
        tomllib.loads((work / "saidby.toml").read_text(encoding="utf-8"))["glossary"]["directory"]
        == []
    )
    assert "none for this run only" not in out.getvalue()
