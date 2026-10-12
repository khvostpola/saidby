# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import yaml

from saidby.errors import InputError
from saidby.evaluation import arbitrate, metrics
from saidby.evaluation.reference import parse_reference
from saidby.evaluation.score import score_run
from saidby.formats.rttm import write_rttm
from saidby.formats.words_json import write_transcript
from saidby.schema.diarization import Turn
from saidby.schema.speakers import SpeakerEntry
from saidby.schema.transcript import Segment, Transcript, Word

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/synthetic/tones_2spk_10s.flac"
jiwer = pytest.importorskip("jiwer")


def _run(tmp_path: Path, name: str, text: str, speaker: str = "ana") -> Path:
    words = [
        Word(start=0.5 + i * 0.7, end=0.5 + i * 0.7 + 0.5, word=f" {w}", speaker="SPEAKER_00")
        for i, w in enumerate(text.split())
    ]
    transcript = Transcript(
        duration_s=10,
        speakers=[SpeakerEntry(label="SPEAKER_00", id=speaker, name=speaker.title())],
        segments=[Segment(start=0.5, end=words[-1].end, words=words)],
    )
    folder = tmp_path / name
    write_transcript(folder / "transcript.words.json", transcript)
    write_rttm(
        folder / "diarization.rttm", "u", [Turn(start=0.5, end=words[-1].end, label=speaker)]
    )
    return folder


def _directory(tmp_path: Path) -> Path:
    path = tmp_path / "directory.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "language": "es",
                "people": [{"id": "ana", "name": "Ana"}],
                "terms": [
                    {"term": "Acme", "variants": ["akme"]},
                    {"term": "parce", "type": "dialect", "variants": ["parse"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_reference_parsing_with_offset_and_speakers() -> None:
    ref = parse_reference(
        "# offset_s: 30\n00:00-00:05 | Ana | hola mundo\n00:05-00:09 | Ben | adios\n"
    )
    assert ref.offset_s == 30
    assert [(r.start, r.end, r.speaker) for r in ref.lines] == [(0, 5, "Ana"), (5, 9, "Ben")]
    assert ref.window == (30, 39)
    assert ref.has_speakers


def test_reference_unknown_speaker_and_bad_lines() -> None:
    assert not parse_reference("00:00-00:05 | ? | hola").has_speakers
    with pytest.raises(InputError):
        parse_reference("not a reference line")
    with pytest.raises(InputError):
        parse_reference("# only comments\n")


def test_reference_splits_inline_turn_changes_at_word_times() -> None:
    words = [
        Word(start=0.0 + i, end=0.8 + i, word=f" {w}")
        for i, w in enumerate(["uno", "dos", "tres", "cuatro"])
    ]
    ref = parse_reference("00:00-00:04 | Ana | uno dos >> Ben tres cuatro", words)
    assert [(r.speaker, r.text) for r in ref.lines] == [("Ana", "uno dos"), ("Ben", "tres cuatro")]
    assert ref.lines[0].end == pytest.approx(2.0)


def test_wer_and_dialect_unification() -> None:
    mapping = {"parse": "parce"}
    result = metrics.score_wer("hola parce vamos", "hola parse vamos", mapping)
    assert result["wer_pct"] == pytest.approx(33.33, abs=0.01)
    assert result["wer_dialect_unified_pct"] == 0.0


def test_term_scoring_counts_min_of_reference_and_hypothesis() -> None:
    from saidby.formats.directory_yaml import validate_directory

    directory = validate_directory(
        {
            "version": 1,
            "language": "es",
            "people": [{"id": "ana", "name": "Ana"}],
            "terms": [{"term": "Acme"}, {"term": "parce", "type": "dialect"}],
        }
    )
    score = metrics.score_terms(directory, "Acme y Ana con Acme", "acme y ana con akme")
    assert (score.in_reference, score.occurrences, score.correct_pct) == (2, 3, 66.67)
    assert score.missed == {"Acme": "1/2"}


def test_score_run_end_to_end(tmp_path: Path) -> None:
    run = _run(tmp_path, "run", "hola Acme con Ana hoy")
    ref = tmp_path / "ref.txt"
    ref.write_text("00:00-00:05 | Ana | hola Acme con Ana hoy\n", encoding="utf-8")
    result = score_run(ref, run, _directory(tmp_path))
    assert result["wer_pct"] == 0.0
    assert result["terms_correct_pct"] == 100.0
    assert result["diarization"]["speech_with_correct_name_pct"] == pytest.approx(66.0, abs=1.0)
    assert "terms_missed" in result


def _arbitration(tmp_path: Path) -> Path:
    candidate = _run(
        tmp_path, "cand", "uno dos tres akme cinco seis siete ocho nueve diez once doce"
    )
    baseline = _run(
        tmp_path, "base", "uno dos tres Acme cinco seis siete ocho nueve diez trece doce"
    )
    ref = tmp_path / "ref.txt"
    ref.write_text(
        "00:00-00:09 | ? | uno dos tres Acme cinco seis siete ocho nueve diez once doce\n",
        encoding="utf-8",
    )
    out = tmp_path / "arb"
    summary = arbitrate.build(out, "call1", "Call 1", FIXTURE, ref, candidate, baseline)
    assert summary["regions"] >= 1
    return out


@pytest.mark.needs_ffmpeg
def test_arbitration_scoring_votes_and_typed_text(tmp_path: Path) -> None:
    out = _arbitration(tmp_path)
    items = json.loads((out / "items.json").read_text(encoding="utf-8"))
    keys = json.loads((out / "keys.json").read_text(encoding="utf-8"))
    assert (out / "clips" / items[0]["clip"]).exists()
    answers = []
    for item in items:
        shown_a = keys[item["id"]]["a"]
        choice = "a" if shown_a == "baseline" else "b"
        answers.append({"id": item["id"], "choice": choice})
    (out / "answers.jsonl").write_text(
        "".join(json.dumps(a) + "\n" for a in answers), encoding="utf-8"
    )
    first = arbitrate.score(out, margin=1.0)[0]
    assert first["judged"] == len(items)
    assert first["votes"]["baseline"] == len(items)
    assert first["delta_wer_pp"] > 0
    assert first["point_estimate_not_worse"] is False
    assert first["non_inferior"] is False


@pytest.mark.needs_ffmpeg
def test_typed_text_overrides_vote_and_ties_are_neutral(tmp_path: Path) -> None:
    out = _arbitration(tmp_path)
    items = json.loads((out / "items.json").read_text(encoding="utf-8"))
    (out / "answers.jsonl").write_text(
        "".join(json.dumps({"id": i["id"], "choice": "neither"}) + "\n" for i in items),
        encoding="utf-8",
    )
    neutral = arbitrate.score(out)[0]
    assert neutral["delta_errors"] == 0
    assert neutral["point_estimate_not_worse"] is True
    (out / "truths.jsonl").write_text(
        "".join(json.dumps({"id": i["id"], "text": "Acme once"}) + "\n" for i in items),
        encoding="utf-8",
    )
    typed = arbitrate.score(out)[0]
    assert sum(typed["typed"].values()) == len(items)
    assert typed["votes"] == dict.fromkeys(typed["votes"], 0)


@pytest.mark.needs_ffmpeg
@pytest.mark.enable_socket
def test_server_endpoints_and_privacy(tmp_path: Path) -> None:
    out = _arbitration(tmp_path)
    server = arbitrate.serve(out, 0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    item = json.loads((out / "items.json").read_text(encoding="utf-8"))[0]

    def post(path: str, body: dict[str, Any]) -> int:
        request = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request) as response:
                return int(response.status)
        except urllib.error.HTTPError as exc:
            return exc.code

    def get(path: str) -> int:
        try:
            with urllib.request.urlopen(base + path) as response:
                return int(response.status)
        except urllib.error.HTTPError as exc:
            return exc.code

    try:
        assert get("/") == 200
        assert get("/items.json") == 200
        assert get(f"/clips/{item['clip']}") == 200
        for hidden in ("/keys.json", "/meta.json", "/answers.jsonl", "/clips/../keys.json"):
            assert get(hidden) == 404
        assert post("/answer", {"id": item["id"], "choice": "a"}) == 200
        assert post("/answer", {"id": item["id"], "choice": "nope"}) == 400
        assert post("/answer", {"id": "unknown", "choice": "a"}) == 400
        assert post("/truth", {"id": item["id"], "text": "Acme"}) == 200
        assert post("/truth", {"id": item["id"], "text": "  "}) == 400
        merged = json.loads(urllib.request.urlopen(base + "/answers").read())
        assert merged[item["id"]] == "text"
    finally:
        server.shutdown()
        server.server_close()
