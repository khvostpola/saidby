# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from dataclasses import dataclass
from pathlib import Path

from saidby.formats.corrections_log import read_corrections
from saidby.schema.manifest import Manifest
from saidby.schema.transcript import Transcript, Word

KINDS = ("diarization", "llm_rejected", "low_confidence")
DEFAULT_LOW_P = 0.6
LOW_GAP_S = 0.5
REVIEW_LOG = "logs/review.jsonl"


@dataclass(frozen=True)
class Item:
    kind: str
    start: float
    end: float
    first: int
    last: int

    def key(self) -> str:
        return f"{self.kind}:{self.start:.2f}:{self.end:.2f}"


def decided_keys(out_dir: Path) -> set[str]:
    path = out_dir / REVIEW_LOG
    if not path.is_file():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("decision") in {"edited", "kept", "speaker"}:
            keys.add(row["key"])
    return keys


def log_decision(out_dir: Path, item: Item, decision: str, speaker: str | None = None) -> None:
    path = out_dir / REVIEW_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, object] = {
        "key": item.key(),
        "kind": item.kind,
        "start": item.start,
        "end": item.end,
        "decision": decision,
    }
    if speaker:
        row["speaker"] = speaker
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _span_to_item(kind: str, words: list[Word], start: float, end: float) -> Item | None:
    inside = [i for i, w in enumerate(words) if start <= (w.start + w.end) / 2 <= end]
    if not inside:
        return None
    return Item(kind, words[inside[0]].start, words[inside[-1]].end, inside[0], inside[-1])


def _diarization_items(manifest: Manifest, words: list[Word]) -> list[Item]:
    spans = (manifest.compare or {}).get("disagreement_spans", [])
    items = [_span_to_item("diarization", words, s["start"], s["end"]) for s in spans]
    return [i for i in items if i is not None]


def _rejected_items(out_dir: Path, words: list[Word]) -> list[Item]:
    items: list[Item] = []
    for c in read_corrections(out_dir / "corrections.jsonl"):
        if (
            c.by != "llm"
            or c.status != "rejected"
            or c.reason == "truncated_response"
            or not c.from_
        ):
            continue
        count = len(c.from_.split())
        starts = [i for i, w in enumerate(words) if abs(w.start - c.t) < 0.05]
        if starts:
            first = starts[0]
            last = min(len(words) - 1, first + count - 1)
            items.append(Item("llm_rejected", words[first].start, words[last].end, first, last))
    return items


def _low_items(words: list[Word], threshold: float) -> list[Item]:
    items: list[Item] = []
    run: list[int] = []
    for i, w in enumerate(words):
        if w.p is not None and w.p < threshold and w.source == "asr":
            if run and w.start - words[run[-1]].end > LOW_GAP_S:
                items.append(_run_item(words, run))
                run = []
            run.append(i)
    if run:
        items.append(_run_item(words, run))
    return items


def _run_item(words: list[Word], run: list[int]) -> Item:
    return Item("low_confidence", words[run[0]].start, words[run[-1]].end, run[0], run[-1])


def build_queue(
    out_dir: Path,
    transcript: Transcript,
    manifest: Manifest,
    *,
    kinds: tuple[str, ...] = KINDS,
    low_p: float = DEFAULT_LOW_P,
) -> list[Item]:
    words = transcript.words()
    candidates = {
        "diarization": _diarization_items(manifest, words) if "diarization" in kinds else [],
        "llm_rejected": _rejected_items(out_dir, words) if "llm_rejected" in kinds else [],
        "low_confidence": _low_items(words, low_p) if "low_confidence" in kinds else [],
    }
    done = decided_keys(out_dir)
    taken: set[int] = {i for i, w in enumerate(words) if w.source == "review"}
    queue: list[Item] = []
    for kind in KINDS:
        for item in sorted(candidates[kind], key=lambda x: x.start):
            span = set(range(item.first, item.last + 1))
            if item.key() in done or span & taken:
                continue
            taken |= span
            queue.append(item)
    return queue
