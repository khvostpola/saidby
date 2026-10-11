# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import re


def slugify(stem: str) -> str:
    slug = re.sub(r"[^\w.-]+", "_", stem).strip("._")[:100]
    return slug or "recording"


def unique_slugs(stems: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    slugs = []
    for stem in stems:
        base = slugify(stem)
        count = seen.get(base, 0) + 1
        seen[base] = count
        slugs.append(base if count == 1 else f"{base}-{count}")
    return slugs


def speaker_label(index: int) -> str:
    return f"SPEAKER_{index:02d}"
