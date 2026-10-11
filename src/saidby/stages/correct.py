# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import difflib
from dataclasses import dataclass
from typing import Any

from saidby.ports.corrector import LlmClient, LlmTruncatedError
from saidby.schema.correction import Correction, Reason
from saidby.schema.directory import Directory
from saidby.schema.transcript import Segment, Transcript, Word
from saidby.stages.glossary.prompts import PromptTemplate, template_for
from saidby.text.normalize import norm

DEFAULT_CHUNK_WORDS = 90
DEFAULT_MAX_SPAN = 3
DEFAULT_MIN_SIMILARITY = 0.5


@dataclass(frozen=True)
class Entry:
    term: str
    is_person: bool
    variants: list[str]
    confusions: list[str]
    context: str


@dataclass
class LlmStats:
    chunks: int = 0
    accepted: int = 0
    rejected: int = 0
    truncated: int = 0


def build_entries(directory: Directory) -> list[Entry]:
    entries = [
        Entry(p.name, True, p.variants, p.confusions, p.context or "") for p in directory.people
    ]
    entries += [
        Entry(t.term, False, t.variants, t.confusions, t.context or "")
        for t in directory.terms
        if t.type != "dialect"
    ]
    return entries


def build_system(template: PromptTemplate, entries: list[Entry]) -> str:
    lines = []
    for e in entries:
        kind = template.kind_person if e.is_person else template.kind_term
        extra = ""
        if e.variants:
            extra += f"; {template.usually_written}: {', '.join(e.variants)}"
        if e.confusions:
            extra += f"; {template.confused_with}: {', '.join(e.confusions)}"
        if e.context:
            extra += f"; {template.context}: {e.context}"
        lines.append(f"- {e.term} ({kind}{extra})")
    return f"{template.system}\n\n{template.directory_title}:\n" + "\n".join(lines)


def build_schema(allowed: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "integer"},
                        "end": {"type": "integer"},
                        "term": {"type": "string", "enum": allowed},
                    },
                    "required": ["start", "end", "term"],
                },
            }
        },
        "required": ["changes"],
    }


def _judge(  # noqa: PLR0911
    chunk: list[Word],
    change: dict[str, Any],
    allowed: set[str],
    known: dict[str, set[str]],
    max_span: int,
    min_similarity: float,
) -> tuple[Reason | None, str | None, float | None]:
    start, end, term = change.get("start"), change.get("end"), change.get("term")
    if not isinstance(start, int) or not isinstance(end, int) or not isinstance(term, str):
        return "out_of_range", None, None
    if not 0 <= start <= end < len(chunk):
        return "out_of_range", None, None
    if end - start + 1 > max_span:
        return "span_too_long", None, None
    if term not in allowed:
        return "term_not_allowed", None, None
    original = " ".join(w.word.strip() for w in chunk[start : end + 1])
    if norm(original) == norm(term):
        return "already_equal", original, None
    accepted_forms = known[term] | {norm(term)}
    if end - start + 1 > len(term.split()) and norm(original) not in accepted_forms:
        return "covers_extra_words", original, None
    similarity = difflib.SequenceMatcher(a=norm(original), b=norm(term)).ratio()
    if norm(original) not in known[term] and similarity < min_similarity:
        return "low_similarity", original, round(similarity, 2)
    return None, original, round(similarity, 2)


def llm_correct(
    transcript: Transcript,
    directory: Directory,
    client: LlmClient,
    *,
    language: str | None,
    chunk_words: int = DEFAULT_CHUNK_WORDS,
    max_span: int = DEFAULT_MAX_SPAN,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> tuple[Transcript, list[Correction], LlmStats]:
    entries = build_entries(directory)
    allowed_list = [e.term for e in entries]
    allowed = set(allowed_list)
    known = {e.term: {norm(v) for v in [*e.variants, *e.confusions]} for e in entries}
    template = template_for(language)
    system = build_system(template, entries)
    schema = build_schema(allowed_list)
    words = transcript.words()
    log: list[Correction] = []
    stats = LlmStats()
    replace_at: dict[int, tuple[int, str] | None] = {}
    for offset in range(0, len(words), chunk_words):
        chunk = words[offset : offset + chunk_words]
        stats.chunks += 1
        numbered = " ".join(f"{i}:{w.word.strip()}" for i, w in enumerate(chunk))
        try:
            reply = client.complete_json(
                system=system, user=template.user + numbered, schema=schema
            )
        except LlmTruncatedError:
            stats.truncated += 1
            log.append(
                Correction(
                    t=round(chunk[0].start, 2),
                    by="llm",
                    status="rejected",
                    reason="truncated_response",
                )
            )
            continue
        for change in reply.get("changes", []):
            reason, original, similarity = _judge(
                chunk, change, allowed, known, max_span, min_similarity
            )
            term = change.get("term") if isinstance(change.get("term"), str) else None
            start = change.get("start") if isinstance(change.get("start"), int) else 0
            end = change.get("end") if isinstance(change.get("end"), int) else start
            first = offset + max(0, start)
            if reason is None and any(
                i in replace_at for i in range(offset + start, offset + end + 1)
            ):
                reason = "overlaps_change"
            at = chunk[min(max(start, 0), len(chunk) - 1)]
            base = {
                "t": round(at.start, 2),
                "from_": original,
                "to": term,
                "by": "llm",
                "similarity": similarity,
            }
            if reason is not None:
                stats.rejected += 1
                log.append(Correction(**base, status="rejected", reason=reason))  # type: ignore[arg-type]
                continue
            assert term is not None
            replace_at[first] = (offset + end, term)
            for i in range(first + 1, offset + end + 1):
                replace_at[i] = None
            stats.accepted += 1
            log.append(Correction(**base, status="accepted"))  # type: ignore[arg-type]
    return _apply(transcript, words, replace_at), log, stats


def _apply(
    transcript: Transcript, words: list[Word], replace_at: dict[int, tuple[int, str] | None]
) -> Transcript:
    index = 0
    segments = []
    for segment in transcript.segments:
        new: list[Word] = []
        for word in segment.words:
            if index not in replace_at:
                new.append(word)
            elif (action := replace_at[index]) is not None:
                last, term = action
                lead = word.word[: len(word.word) - len(word.word.lstrip())] or " "
                new.append(
                    word.model_copy(
                        update={"end": words[last].end, "word": lead + term, "source": "llm"}
                    )
                )
            index += 1
        segments.append(Segment(start=segment.start, end=segment.end, words=new))
    return transcript.model_copy(update={"segments": segments})
