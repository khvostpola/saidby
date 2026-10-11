# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import datetime as dt
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from saidby.formats.audio import SAMPLE_RATE
from saidby.formats.directory_yaml import decode_vector, encode_vector
from saidby.ports.embedder import Embedder
from saidby.schema.diarization import Diarization
from saidby.schema.directory import ConsentRecord, ConsentRef, Directory, Voiceprint
from saidby.schema.speakers import IdentificationResult, SpeakerIdentity

DEFAULT_MIN_SEGMENT_S = 1.5
DEFAULT_TARGET_S = 60.0
DEFAULT_THRESHOLD = 0.5
DEFAULT_MIN_SPEECH_S = 3.0


@dataclass(frozen=True)
class Centroid:
    vector: np.ndarray
    seconds: float


def pick_spans(
    spans: list[tuple[float, float]], min_segment_s: float, target_s: float
) -> list[tuple[float, float]]:
    usable = sorted(
        (s for s in spans if s[1] - s[0] >= min_segment_s), key=lambda s: s[1] - s[0], reverse=True
    )
    chosen: list[tuple[float, float]] = []
    total = 0.0
    for span in usable:
        if total >= target_s:
            break
        chosen.append(span)
        total += span[1] - span[0]
    return chosen


def speaker_centroids(
    audio: np.ndarray,
    spans_by_label: dict[str, list[tuple[float, float]]],
    embedder: Embedder,
    *,
    min_segment_s: float = DEFAULT_MIN_SEGMENT_S,
    target_s: float = DEFAULT_TARGET_S,
) -> dict[str, Centroid]:
    centroids: dict[str, Centroid] = {}
    for label, spans in sorted(spans_by_label.items()):
        chosen = pick_spans(spans, min_segment_s, target_s)
        if not chosen:
            continue
        vectors = embedder.embed(audio, chosen)
        weights = np.array([e - s for s, e in chosen])
        mean = np.average(vectors, axis=0, weights=weights)
        centroids[label] = Centroid(
            (mean / np.linalg.norm(mean)).astype(np.float32), round(float(weights.sum()), 1)
        )
    return centroids


def usable_voiceprints(
    directory: Directory, embedder: Embedder
) -> tuple[dict[str, np.ndarray], list[str]]:
    enrolled: dict[str, np.ndarray] = {}
    warnings: list[str] = []
    models = {embedder.info.model, embedder.info.repo_id}
    for person in directory.people:
        vp = person.voiceprint
        if vp is None:
            continue
        compatible = (
            vp.model in models
            and vp.revision == embedder.info.revision
            and vp.preprocessing in embedder.accepted_preprocessing
        )
        if compatible:
            enrolled[person.id] = decode_vector(vp.vector)
        else:
            warnings.append(
                f"voiceprint of {person.id} was made with {vp.model}@{vp.revision[:8]}, "
                f"current embedder is {embedder.info.model}@{(embedder.info.revision or '')[:8]}; "
                "enroll again"
            )
    return enrolled, warnings


def assign(
    centroids: dict[str, Centroid],
    enrolled: dict[str, np.ndarray],
    speech_s: dict[str, float],
    names: dict[str, str],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    min_speech_s: float = DEFAULT_MIN_SPEECH_S,
) -> dict[str, SpeakerIdentity]:
    labels = sorted(speech_s)
    people = sorted(enrolled)
    scores = {
        label: {p: float(np.dot(centroids[label].vector, enrolled[p])) for p in people}
        for label in labels
        if label in centroids
    }
    chosen: dict[str, str] = {}
    scored = [label for label in labels if label in scores]
    if scored and people:
        matrix = np.array([[scores[label][p] for p in people] for label in scored])
        rows, cols = linear_sum_assignment(-matrix)
        chosen = {scored[r]: people[c] for r, c in zip(rows, cols, strict=True)}
    mapping: dict[str, SpeakerIdentity] = {}
    for label in labels:
        person = chosen.get(label)
        accepted = (
            person is not None
            and scores[label][person] >= threshold
            and speech_s[label] >= min_speech_s
        )
        mapping[label] = SpeakerIdentity(
            label=label,
            person_id=person if accepted else None,
            name=names.get(person) if accepted and person else None,
            score=round(scores[label][person], 3) if person else None,
            speech_s=round(speech_s[label], 1),
            all_scores={p: round(v, 3) for p, v in scores.get(label, {}).items()},
        )
    return mapping


def identify(
    audio: np.ndarray,
    diarization: Diarization,
    directory: Directory,
    embedder: Embedder,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    min_speech_s: float = DEFAULT_MIN_SPEECH_S,
) -> IdentificationResult:
    enrolled, warnings = usable_voiceprints(directory, embedder)
    spans = {
        label: [(t.start, t.end) for t in diarization.exclusive_turns if t.label == label]
        for label in diarization.labels()
    }
    speech = {label: sum(e - s for s, e in sp) for label, sp in spans.items()}
    centroids = speaker_centroids(audio, spans, embedder) if enrolled else {}
    names = {p.id: p.name for p in directory.people}
    mapping = assign(
        centroids, enrolled, speech, names, threshold=threshold, min_speech_s=min_speech_s
    )
    return IdentificationResult(
        mapping=mapping, warnings=warnings, voiceprints_skipped=len(warnings)
    )


def make_voiceprint(
    centroid: Centroid,
    embedder: Embedder,
    *,
    channel: str,
    consent: ConsentRecord,
    now: dt.datetime | None = None,
) -> Voiceprint:
    return Voiceprint(
        model=embedder.info.model,
        revision=embedder.info.revision or "",
        dim=int(centroid.vector.shape[-1]),
        sample_rate=SAMPLE_RATE,
        preprocessing=embedder.preprocessing,
        channel=channel,
        seconds=centroid.seconds,
        vector=encode_vector(centroid.vector),
        enrolled_at=now or dt.datetime.now(dt.UTC).replace(microsecond=0),
        consent=ConsentRef(declared_by=consent.declared_by, date=consent.date),
    )
