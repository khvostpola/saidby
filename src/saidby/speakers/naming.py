# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import re
import unicodedata
from collections.abc import Iterable

from saidby.schema.speakers import SpeakerEntry


def track_path(entry: SpeakerEntry) -> str:
    return f"speakers/{entry.file_id}.flac"


def ascii_slug(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")[:64].strip("-")


def person_id_for(name: str, taken: Iterable[str] = ()) -> str:
    base = ascii_slug(name) or "speaker"
    used = set(taken)
    candidate, count = base, 1
    while candidate in used:
        count += 1
        candidate = f"{base[:60].strip('-')}-{count}"
    return candidate
