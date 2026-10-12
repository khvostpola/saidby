# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
import re
import shutil
from pathlib import Path

import pytest

from saidby.cli.progress import Progress
from saidby.config.settings import Settings
from saidby.engines.diarize.fake import FakeDiarizer
from saidby.formats.words_json import read_transcript
from saidby.models import get_spec
from saidby.models import store as model_store
from saidby.pipeline.runner import Pipeline

CONV = Path(__file__).resolve().parents[2] / "fixtures/conversations/dev/dev-conv-01"

pytestmark = [
    pytest.mark.models,
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed"),
    pytest.mark.skipif(
        not model_store.is_installed(get_spec("asr:tiny")), reason="asr:tiny is not pulled"
    ),
]


def _normalize(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


def test_tiny_transcribes_clean_conversation_offline(tmp_path: Path) -> None:
    jiwer = pytest.importorskip("jiwer")
    settings = Settings(device="cpu", language="es", asr_model="tiny")
    pipeline = Pipeline(
        settings,
        diarizer=FakeDiarizer(rttm=CONV.with_suffix(".rttm")),
        progress=Progress("none"),
    )
    results = pipeline.run([CONV.with_suffix(".flac")], tmp_path)
    assert results[0].status == "ok"
    transcript = read_transcript(tmp_path / "dev-conv-01" / "transcript.words.json")
    expected = json.loads(CONV.with_suffix(".expected.json").read_text(encoding="utf-8"))["text"]
    hypothesis = " ".join(w.word for w in transcript.words())
    wer = jiwer.wer(" ".join(_normalize(expected)), " ".join(_normalize(hypothesis)))
    assert wer < 0.6
    assert {s.label for s in transcript.speakers} == {
        t["speaker"]
        for t in json.loads(CONV.with_suffix(".expected.json").read_text(encoding="utf-8"))["turns"]
    }
