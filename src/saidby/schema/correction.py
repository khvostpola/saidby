# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

CorrectionBy = Literal["dialect", "llm", "bias", "review"]
Reason = Literal[
    "out_of_range",
    "span_too_long",
    "term_not_allowed",
    "already_equal",
    "covers_extra_words",
    "low_similarity",
    "overlaps_change",
    "truncated_response",
]


class Correction(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    t: float
    end: float | None = None
    from_: str | None = Field(
        default=None,
        validation_alias=AliasChoices("from", "from_"),
        serialization_alias="from",
    )
    to: str | None = None
    by: CorrectionBy
    status: Literal["accepted", "rejected"]
    reason: Reason | None = None
    similarity: float | None = None
