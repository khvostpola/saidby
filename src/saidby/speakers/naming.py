# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

from saidby.schema.speakers import SpeakerEntry


def track_path(entry: SpeakerEntry) -> str:
    return f"speakers/{entry.file_id}.flac"
