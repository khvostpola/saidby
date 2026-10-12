# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import re

RESERVED_NAMES = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{n}" for n in range(1, 10)),
        *(f"lpt{n}" for n in range(1, 10)),
    }
)


def safe_filename(name: str) -> str:
    """Keep a file name creatable on Windows, where device names are reserved."""
    stem, dot, rest = name.partition(".")
    return f"{stem}_{dot}{rest}" if stem.lower() in RESERVED_NAMES else name


def slugify(stem: str) -> str:
    slug = re.sub(r"[^\w.-]+", "_", stem).strip("._")[:100]
    return safe_filename(slug or "recording")


def unique_slugs(stems: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    slugs = []
    for stem in stems:
        base = slugify(stem)
        key = base.casefold()
        count = seen.get(key, 0) + 1
        seen[key] = count
        slugs.append(base if count == 1 else f"{base}-{count}")
    return slugs


def speaker_label(index: int) -> str:
    return f"SPEAKER_{index:02d}"
