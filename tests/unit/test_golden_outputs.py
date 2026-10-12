# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

"""The files saidby writes are the same bytes on every system: UTF-8, LF, forward slashes."""

from pathlib import Path

from saidby.config.writer import render_config, update_config
from saidby.formats.corrections_log import write_corrections
from saidby.formats.rttm import write_rttm
from saidby.formats.transcripts import render_txt, render_vtt
from saidby.formats.words_json import write_transcript
from saidby.formats.yaml_io import save_yaml
from saidby.schema.correction import Correction
from saidby.schema.diarization import Turn
from saidby.schema.speakers import SpeakerEntry
from saidby.schema.transcript import Segment, Transcript, Word


def _transcript() -> Transcript:
    words = [
        Word(start=0.0, end=0.4, word=" Hola", speaker="SPEAKER_00"),
        Word(start=0.5, end=0.9, word=" Gómez", speaker="SPEAKER_00", p=0.42),
        Word(start=1.2, end=1.6, word=" ¿qué", speaker="SPEAKER_01"),
        Word(start=1.7, end=2.0, word=" más?", speaker="SPEAKER_01"),
    ]
    ana = SpeakerEntry(
        label="SPEAKER_00", id="ana-gomez", name="Ana Gómez", track="speakers/ana-gomez.flac"
    )
    return Transcript(
        language="es",
        duration_s=2.0,
        speakers=[ana, SpeakerEntry(label="SPEAKER_01")],
        segments=[Segment(start=0.0, end=2.0, words=words)],
    )


TXT = "[00:00:00] Ana Gómez: Hola Gómez\n[00:00:01] SPEAKER_01: ¿qué más?\n".encode()
VTT = (
    "WEBVTT\n\n00:00:00.000 --> 00:00:00.900\n<v Ana Gómez>Hola Gómez\n\n"
    "00:00:01.200 --> 00:00:02.000\n<v SPEAKER_01>¿qué más?\n"
).encode()
RTTM = (
    b"SPEAKER call 1 0.000 0.900 <NA> <NA> SPEAKER_00 <NA> <NA>\n"
    b"SPEAKER call 1 1.200 0.800 <NA> <NA> SPEAKER_01 <NA> <NA>\n"
)
JSONL = (
    b'{"t":0.5,"end":0.9,"from":"Gomes","to":"G\xc3\xb3mez","by":"review","status":"accepted"}\n'
)
YAML = "version: 1\nlanguage: es\npeople:\n  - id: ana-gomez\n    name: Ana Gómez\n".encode()
TOML = (
    b"# saidby settings. Command-line flags override them.\n\n"
    b'[saidby]\nlanguage = "es"\nout = "saidby"\n\n'
    b"[glossary]\n# Far to near: a later file wins over an earlier one.\n"
    b'directory = ["~/shared/directory.yaml", "directory.yaml"]\n'
)
TOML_UPDATED = (
    b"# saidby settings. Command-line flags override them.\n\n"
    b'[saidby]\nlanguage = "es"\nout = "saidby"\n\n'
    b'[glossary]\ndirectory = ["~/shared/directory.yaml"]\n'
)
JSON_HEAD = b'{\n "schema": "saidby.words/1",\n "language": "es",\n "duration_s": 2.0,\n'
JSON_WORD = b'     "word": " G\xc3\xb3mez",\n     "p": 0.42,\n'


def test_transcript_text_and_captions() -> None:
    assert render_txt(_transcript()).encode() == TXT
    assert render_vtt(_transcript()).encode() == VTT


def test_words_json(tmp_path: Path) -> None:
    write_transcript(tmp_path / "transcript.words.json", _transcript())
    data = (tmp_path / "transcript.words.json").read_bytes()
    assert data.startswith(JSON_HEAD)
    assert JSON_WORD in data
    assert b'"track": "speakers/ana-gomez.flac"' in data
    assert b"\r" not in data


def test_rttm_and_corrections(tmp_path: Path) -> None:
    turns = [
        Turn(start=1.2, end=2.0, label="SPEAKER_01"),
        Turn(start=0.0, end=0.9, label="SPEAKER_00"),
    ]
    write_rttm(tmp_path / "x.rttm", "call", turns)
    assert (tmp_path / "x.rttm").read_bytes() == RTTM
    fix = Correction(t=0.5, end=0.9, from_="Gomes", to="Gómez", by="review", status="accepted")
    write_corrections(tmp_path / "c.jsonl", [fix])
    assert (tmp_path / "c.jsonl").read_bytes() == JSONL


def test_yaml_and_toml(tmp_path: Path) -> None:
    people = [{"id": "ana-gomez", "name": "Ana Gómez"}]
    save_yaml(tmp_path / "d.yaml", {"version": 1, "language": "es", "people": people}, backup=False)
    assert (tmp_path / "d.yaml").read_bytes() == YAML
    rendered = render_config(
        language="es", directories=["~/shared/directory.yaml", "directory.yaml"], out="saidby"
    )
    assert rendered.encode() == TOML
    config = tmp_path / "saidby.toml"
    update_config(config, language="es", out="saidby", directory=["~/shared/directory.yaml"])
    assert config.read_bytes() == TOML_UPDATED
