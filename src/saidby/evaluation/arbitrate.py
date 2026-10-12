# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import difflib
import json
import random
import re
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any

import numpy as np

from saidby.errors import InputError
from saidby.evaluation.metrics import dialect_map, load_run, words_text
from saidby.evaluation.reference import parse_reference
from saidby.formats.directory_yaml import load_directory
from saidby.i18n import _
from saidby.schema.transcript import Transcript
from saidby.stages.ingest import ingest

SAMPLE_RATE = 16000
EDGE_S = 1.0
PAD_S = 1.0
MERGE_GAP = 2
CONTEXT = 6
CHOICES = {"a", "b", "both", "neither"}
SYSTEMS = ("candidate", "baseline")
BOOTSTRAP = 10_000
Token = tuple[str, float, float]


def tokens(
    transcript: Transcript, window: tuple[float, float], mapping: dict[str, str]
) -> list[Token]:
    result: list[Token] = []
    for word in transcript.words():
        if window[0] <= word.start < window[1]:
            for tok in words_text(word.word).split():
                result.append((mapping.get(tok, tok), word.start, word.end))
    return result


def regions(a: list[Token], b: list[Token]) -> list[list[int]]:
    matcher = difflib.SequenceMatcher(a=[t[0] for t in a], b=[t[0] for t in b], autojunk=False)
    merged: list[list[int]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if merged and i1 - merged[-1][1] < MERGE_GAP and j1 - merged[-1][3] < MERGE_GAP:
            merged[-1][1], merged[-1][3] = i2, j2
        else:
            merged.append([i1, i2, j1, j2])
    return merged


def levenshtein(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def side(toks: list[Token], lo: int, hi: int) -> dict[str, list[str]]:
    return {
        "before": [t[0] for t in toks[max(0, lo - CONTEXT) : lo]],
        "diff": [t[0] for t in toks[lo:hi]],
        "after": [t[0] for t in toks[hi : hi + CONTEXT]],
    }


def write_clip(path: Path, audio: np.ndarray, start: float, end: float) -> None:
    pcm = (np.clip(audio[int(start * SAMPLE_RATE) : int(end * SAMPLE_RATE)], -1, 1) * 32767).astype(
        np.int16
    )
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SAMPLE_RATE)
        fh.writeframes(pcm.tobytes())


def _load(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def build(
    out: Path,
    name: str,
    label: str,
    media: Path,
    reference: Path,
    candidate: Path,
    baseline: Path,
    directory: Path | None = None,
    seed: int = 7,
) -> dict[str, Any]:
    cand_run, base_run = load_run(candidate), load_run(baseline)
    ref = parse_reference(reference.read_text(encoding="utf-8"), cand_run.words())
    window = ref.window
    mapping = dialect_map(load_directory(directory)[0] if directory else None)
    cand = tokens(cand_run, window, mapping)
    base = tokens(base_run, window, mapping)
    audio = ingest(media, out / ".ingest").audio
    rng = random.Random(seed)
    found = []
    for i1, i2, j1, j2 in regions(cand, base):
        times = [t for toks, lo, hi in ((cand, i1, i2), (base, j1, j2)) for t in toks[lo:hi]]
        start, end = min(t[1] for t in times), max(t[2] for t in times)
        if start < window[0] + EDGE_S or end > window[1] - EDGE_S:
            continue
        found.append((i1, i2, j1, j2, start, end))
    rng.shuffle(found)

    (out / "clips").mkdir(parents=True, exist_ok=True)
    items = [i for i in _load(out / "items.json", []) if i["call"] != name]
    keys = {k: v for k, v in _load(out / "keys.json", {}).items() if not k.startswith(f"{name}-")}
    meta = _load(out / "meta.json", {})
    duration = len(audio) / SAMPLE_RATE
    for rank, (i1, i2, j1, j2, start, end) in enumerate(found):
        item_id = f"{name}-{rank:03d}"
        shown_a = rng.choice(SYSTEMS)
        views = {"candidate": side(cand, i1, i2), "baseline": side(base, j1, j2)}
        shown_b = next(s for s in SYSTEMS if s != shown_a)
        clip_start, clip_end = max(0.0, start - PAD_S), min(duration, end + PAD_S)
        write_clip(out / "clips" / f"{item_id}.wav", audio, clip_start, clip_end)
        items.append(
            {
                "id": item_id,
                "call": name,
                "label": label,
                "rank": rank,
                "clip": f"{item_id}.wav",
                "seconds": round(clip_end - clip_start, 1),
                "a": views[shown_a],
                "b": views[shown_b],
            }
        )
        keys[item_id] = {
            "a": shown_a,
            "cost": levenshtein(views["candidate"]["diff"], views["baseline"]["diff"]),
        }
    summary = {
        "label": label,
        "ref_words": len(words_text(ref.text).split()),
        "regions": len(found),
        "candidate": str(candidate),
        "baseline": str(baseline),
    }
    meta[name] = summary
    (out / "items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    (out / "keys.json").write_text(json.dumps(keys, indent=1), encoding="utf-8")
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"call": name, "regions": len(found), "ref_words": summary["ref_words"]}


def _jsonl_last(path: Path, field: str) -> dict[str, str]:
    result: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            result[row["id"]] = row[field]
    return result


def load_answers(out: Path) -> dict[str, str]:
    return _jsonl_last(out / "answers.jsonl", "choice")


def load_truths(out: Path, mapping: dict[str, str]) -> dict[str, list[str]]:
    raw = _jsonl_last(out / "truths.jsonl", "text")
    return {
        i: [" ".join(mapping.get(t, t) for t in words_text(text).split())]
        for i, text in raw.items()
    }


class Handler(BaseHTTPRequestHandler):
    out = Path("arbitration")

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        clip = re.fullmatch(r"/clips/([\w-]+\.wav)", self.path)
        if self.path in ("/", "/index.html"):
            page = resources.files("saidby.evaluation").joinpath("arbitrate.html").read_bytes()
            self._send(page, "text/html; charset=utf-8")
        elif self.path == "/items.json":
            self._send((self.out / "items.json").read_bytes(), "application/json")
        elif self.path == "/answers":
            merged = {
                **load_answers(self.out),
                **dict.fromkeys(_jsonl_last(self.out / "truths.jsonl", "text"), "text"),
            }
            self._send(json.dumps(merged).encode(), "application/json")
        elif clip and (self.out / "clips" / clip[1]).is_file():
            self._send((self.out / "clips" / clip[1]).read_bytes(), "audio/wav")
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path not in ("/answer", "/truth"):
            self.send_error(404)
            return
        row = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        valid = {i["id"] for i in json.loads((self.out / "items.json").read_text())}
        field, allowed = ("choice", CHOICES) if self.path == "/answer" else ("text", None)
        value = row.get(field)
        bad = row.get("id") not in valid or not isinstance(value, str)
        if (
            bad
            or (allowed is not None and value not in allowed)
            or (allowed is None and not value.strip())
        ):
            self.send_error(400)
            return
        name = "answers.jsonl" if allowed is not None else "truths.jsonl"
        with (self.out / name).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": row["id"], field: value}, ensure_ascii=False) + "\n")
        self._send(b"{}", "application/json")

    def log_message(self, *args: Any) -> None:
        return None


def serve(out: Path, port: int = 8765) -> ThreadingHTTPServer:
    if not (out / "items.json").exists():
        raise InputError(
            _("nothing to serve in {out}; run `saidby eval arbitrate-build` first").format(out=out)
        )
    Handler.out = out
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def score(
    out: Path,
    directory: Path | None = None,
    margin: float | None = None,
    seed: int = 7,
) -> list[dict[str, Any]]:
    items = {i["id"]: i for i in json.loads((out / "items.json").read_text())}
    keys = json.loads((out / "keys.json").read_text())
    meta = json.loads((out / "meta.json").read_text())
    mapping = dialect_map(load_directory(directory)[0] if directory else None)
    answers = load_answers(out)
    truths = load_truths(out, mapping)
    rng = np.random.default_rng(seed)
    results: list[dict[str, Any]] = []
    pooled_errors = 0.0
    pooled_boot = np.zeros(BOOTSTRAP)
    pooled_words = 0
    for call, info in meta.items():
        votes = dict.fromkeys((*SYSTEMS, "both", "neither"), 0)
        typed = dict.fromkeys((*SYSTEMS, "tie"), 0)
        contribution: list[float] = []
        for item_id, item in items.items():
            if item["call"] != call or not (item_id in truths or item_id in answers):
                continue
            key = keys[item_id]
            shown_b = next(s for s in SYSTEMS if s != key["a"])
            if item_id in truths:
                diffs = {key["a"]: item["a"]["diff"], shown_b: item["b"]["diff"]}
                errors = {s: levenshtein(diffs[s], truths[item_id][0].split()) for s in SYSTEMS}
                delta = errors["candidate"] - errors["baseline"]
                typed["candidate" if delta < 0 else "baseline" if delta > 0 else "tie"] += 1
            else:
                winner = {"a": key["a"], "b": shown_b}.get(answers[item_id], answers[item_id])
                votes[winner] += 1
                delta = key["cost"] * ((winner == "baseline") - (winner == "candidate"))
            contribution.append(float(delta))
        if not contribution:
            results.append({"call": call, "judged": 0})
            continue
        values = np.array(contribution)
        expand = info["regions"] / len(values)
        errors_total = float(values.sum() * expand)
        boot = rng.choice(values, size=(BOOTSTRAP, len(values))).sum(axis=1) * expand
        pooled_errors += errors_total
        pooled_boot += boot
        pooled_words += info["ref_words"]
        results.append(_row(call, len(values), info, votes, typed, errors_total, boot, margin))
    judged = [r for r in results if r.get("judged")]
    if len(judged) > 1:
        results.append(_summary("all", pooled_errors, pooled_boot, pooled_words, margin))
    return results


def _summary(
    call: str, errors: float, boot: np.ndarray, words: int, margin: float | None
) -> dict[str, Any]:
    scale = 100 / words
    low, high = (float(np.percentile(boot, q)) * scale for q in (2.5, 97.5))
    row: dict[str, Any] = {
        "call": call,
        "delta_errors": round(errors, 1),
        "delta_wer_pp": round(errors * scale, 2),
        "delta_wer_ci95": [round(low, 2), round(high, 2)],
        "point_estimate_not_worse": errors <= 0,
    }
    if margin is not None:
        row["margin_pp"] = margin
        row["non_inferior"] = high < margin
    return row


def _row(
    call: str,
    judged: int,
    info: dict[str, Any],
    votes: dict[str, int],
    typed: dict[str, int],
    errors: float,
    boot: np.ndarray,
    margin: float | None,
) -> dict[str, Any]:
    return {
        **_summary(call, errors, boot, info["ref_words"], margin),
        "judged": judged,
        "regions": info["regions"],
        "ref_words": info["ref_words"],
        "votes": votes,
        "typed": typed,
    }
