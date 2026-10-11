# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import gc
import time
from pathlib import Path

from saidby.errors import UsageError
from saidby.models import ModelSpec, get_spec
from saidby.models import store as model_store


def resolve_model(role: str, name: str) -> tuple[ModelSpec | None, Path, str]:
    key = name if ":" in name else f"{role}:{name}"
    try:
        spec = get_spec(key)
    except UsageError:
        candidate = Path(name)
        if candidate.exists():
            return None, candidate, "local"
        raise
    return spec, model_store.local_path(spec), spec.key.split(":", 1)[1]


def release_memory() -> None:
    gc.collect()
    import sys

    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()


class Stopwatch:
    def __enter__(self) -> "Stopwatch":
        self.start = time.perf_counter()
        self.seconds = 0.0
        return self

    def __exit__(self, *exc: object) -> None:
        self.seconds = round(time.perf_counter() - self.start, 3)
