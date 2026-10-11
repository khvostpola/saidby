# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from saidby.schema.engine import EngineInfo
from saidby.schema.speakers import SpeakerEntry

WordSource = Literal["asr", "bias", "dialect", "llm", "review"]


class Word(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: float
    end: float
    word: str
    p: float | None = None
    speaker: str | None = None
    source: WordSource = "asr"


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: float
    end: float
    words: list[Word]

    @property
    def text(self) -> str:
        return "".join(w.word for w in self.words).strip()


class Transcript(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal["saidby.words/1"] = Field(default="saidby.words/1", alias="schema")
    language: str | None = None
    duration_s: float
    engine: EngineInfo | None = None
    speakers: list[SpeakerEntry] = []
    segments: list[Segment]

    def words(self) -> list[Word]:
        return [w for s in self.segments for w in s.words]
