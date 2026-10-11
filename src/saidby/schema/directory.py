# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PERSON_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"


class ConsentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    declared_by: str
    date: dt.date
    scope: Literal["voiceprint"] = "voiceprint"


class Voiceprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    revision: str
    dim: int
    sample_rate: int
    preprocessing: str
    channel: str
    seconds: float
    vector: str
    enrolled_at: dt.datetime | None = None
    consent: ConsentRef | None = None


class Person(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=PERSON_ID_PATTERN)
    name: str = Field(min_length=1)
    aliases: list[str] = []
    variants: list[str] = []
    confusions: list[str] = []
    context: str | None = None
    voiceprint: Voiceprint | None = None


class Term(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1)
    type: Literal["dialect"] | None = None
    variants: list[str] = []
    confusions: list[str] = []
    context: str | None = None


class Directory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    language: str
    people: list[Person] = []
    terms: list[Term] = []

    @model_validator(mode="after")
    def _unique(self) -> "Directory":
        ids = [p.id for p in self.people]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate person id")
        terms = [t.term.casefold() for t in self.terms]
        if len(terms) != len(set(terms)):
            raise ValueError("duplicate term")
        return self

    def person(self, person_id: str) -> Person | None:
        return next((p for p in self.people if p.id == person_id), None)


class ConsentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person: str
    scope: Literal["voiceprint"] = "voiceprint"
    source: str
    declared_by: str
    date: dt.date

    @field_validator("person")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("person must not be empty")
        return value
