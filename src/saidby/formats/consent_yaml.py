# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import datetime as dt
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml.comments import CommentedSeq

from saidby.errors import InputError
from saidby.formats.directory_yaml import plain
from saidby.formats.yaml_io import load_yaml, save_yaml
from saidby.i18n import _
from saidby.schema.directory import ConsentRecord


def load_consents(path: Path) -> tuple[list[ConsentRecord], Any]:
    if not path.is_file():
        return [], CommentedSeq()
    raw = load_yaml(path)
    if raw is None:
        return [], CommentedSeq()
    try:
        return [ConsentRecord.model_validate(plain(item)) for item in raw], raw
    except ValidationError as exc:
        first = exc.errors()[0]
        raise InputError(_("invalid consent file: {msg}").format(msg=first["msg"])) from exc


def find_consent(records: list[ConsentRecord], *keys: str) -> ConsentRecord | None:
    wanted = {k.casefold() for k in keys if k}
    return next(
        (r for r in records if r.scope == "voiceprint" and r.person.casefold() in wanted), None
    )


def append_consent(path: Path, raw: Any, record: ConsentRecord) -> None:
    raw.append(
        {
            "person": record.person,
            "scope": record.scope,
            "source": record.source,
            "declared_by": record.declared_by,
            "date": record.date
            if isinstance(record.date, dt.date)
            else dt.date.fromisoformat(str(record.date)),
        }
    )
    save_yaml(path, raw)
