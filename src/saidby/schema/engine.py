# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Literal

from pydantic import BaseModel, ConfigDict


class EngineInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["asr", "diarizer", "embedder", "llm"]
    name: str
    model: str
    repo_id: str | None = None
    revision: str | None = None
    device: Literal["cuda", "cpu"] | None = None
    compute_type: str | None = None
    library: str | None = None
