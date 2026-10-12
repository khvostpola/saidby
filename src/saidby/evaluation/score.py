# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Any

from saidby.errors import InputError
from saidby.evaluation import metrics
from saidby.evaluation.reference import parse_reference
from saidby.formats.directory_yaml import load_directory


def score_run(
    reference_path: Path, run_dir: Path, directory_path: Path | None = None
) -> dict[str, Any]:
    if not reference_path.is_file():
        raise InputError(f"reference not found: {reference_path}")
    transcript = metrics.load_run(run_dir)
    reference = parse_reference(reference_path.read_text(encoding="utf-8"), transcript.words())
    directory = load_directory(directory_path)[0] if directory_path else None
    window = reference.window
    hypothesis = "".join(w.word for w in metrics.window_words(transcript, window))
    mapping = metrics.dialect_map(directory)
    result: dict[str, Any] = {
        "window_s": [round(window[0], 1), round(window[1], 1)],
        "ref_words": len(metrics.words_text(reference.text).split()),
        **metrics.score_wer(reference.text, hypothesis, mapping),
    }
    if directory is not None:
        terms = metrics.score_terms(directory, reference.text, hypothesis)
        result.update(
            terms_in_reference=terms.in_reference,
            term_occurrences=terms.occurrences,
            terms_correct_pct=terms.correct_pct,
            terms_missed=terms.missed,
        )
    if reference.has_speakers and (run_dir / "diarization.rttm").is_file():
        result["diarization"] = metrics.score_diarization(reference, run_dir, transcript)
    return result
