# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel, ConfigDict


class SpeakerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    id: str | None = None
    name: str | None = None
    identified: bool = False
    score: float | None = None
    speech_s: float = 0.0
    track: str | None = None
    merged_from: list[str] = []

    @property
    def display(self) -> str:
        return self.name or self.id or self.label

    @property
    def file_id(self) -> str:
        return self.id or self.label


class SpeakerIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    person_id: str | None = None
    name: str | None = None
    score: float | None = None
    speech_s: float = 0.0
    all_scores: dict[str, float] = {}


class IdentificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapping: dict[str, SpeakerIdentity]
    warnings: list[str] = []
    voiceprints_skipped: int = 0
