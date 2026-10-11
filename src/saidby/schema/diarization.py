# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from saidby.schema.engine import EngineInfo


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: float
    end: float
    label: str


def make_exclusive(turns: list[Turn]) -> list[Turn]:
    result: list[Turn] = []
    covered = 0.0
    for turn in sorted(turns, key=lambda t: (t.start, t.end)):
        start = max(turn.start, covered)
        if turn.end > start:
            result.append(Turn(start=start, end=turn.end, label=turn.label))
            covered = turn.end
    return result


class Diarization(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal["saidby.diarization/1"] = Field(default="saidby.diarization/1", alias="schema")
    uri: str
    engine: EngineInfo | None = None
    turns: list[Turn]
    exclusive_turns: list[Turn]

    def labels(self) -> list[str]:
        return sorted({t.label for t in self.turns})

    def speech_s(self, label: str | None = None) -> float:
        return sum(t.end - t.start for t in self.exclusive_turns if label in (None, t.label))

    def overlap_s(self) -> float:
        return max(0.0, sum(t.end - t.start for t in self.turns) - self.speech_s())
