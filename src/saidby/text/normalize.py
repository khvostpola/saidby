# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import re
import unicodedata


def norm(text: str) -> str:
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFC", text.lower()))
