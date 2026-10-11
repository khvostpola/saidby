# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path

import pytest

from saidby.cli.progress import Progress
from saidby.config.settings import Settings
from saidby.formats.manifest import read_manifest
from saidby.formats.words_json import read_transcript
from saidby.pipeline.runner import Pipeline

pytestmark = pytest.mark.gpu

MEDIA = os.environ.get("SAIDBY_TEST_MEDIA")


@pytest.mark.skipif(not MEDIA, reason="set SAIDBY_TEST_MEDIA to a local recording")
def test_default_pipeline_on_local_recording(tmp_path: Path) -> None:
    assert MEDIA is not None
    settings = Settings(device="cuda", language=os.environ.get("SAIDBY_TEST_LANGUAGE", "es"))
    results = Pipeline(settings, progress=Progress("none")).run([Path(MEDIA)], tmp_path)
    assert results[0].status == "ok"
    manifest = read_manifest(tmp_path / results[0].slug / "manifest.json")
    transcript = read_transcript(tmp_path / results[0].slug / "transcript.words.json")
    assert len(transcript.speakers) >= 1
    assert all(w.speaker for w in transcript.words())
    asr = next(s for s in manifest.stages if s.stage == "asr")
    assert asr.wall_s / manifest.audio.duration_s < 0.3
