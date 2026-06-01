"""Application version and update metadata."""
from __future__ import annotations

import re
from dataclasses import dataclass


APP_NAME = "TAFSQ"
APP_VERSION = "1.0.8"
UPDATE_MANIFEST_URL = "http://107.174.62.19/tafsq/update.json"


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    url: str
    filename: str = ""
    notes: str = ""
    sha256: str = ""
    size: int = 0
    mandatory: bool = False


def parse_version(version: str) -> tuple:
    """Parse a semantic-ish version string into comparable parts."""
    parts: list[int | str] = []
    for token in re.split(r"[.\-+_]", str(version).strip()):
        if not token:
            continue
        if token.isdigit():
            parts.append(int(token))
        else:
            match = re.match(r"^(\d+)([A-Za-z].*)$", token)
            if match:
                parts.append(int(match.group(1)))
                parts.append(match.group(2).lower())
            else:
                parts.append(token.lower())
    return tuple(parts)


def is_newer_version(remote: str, current: str = APP_VERSION) -> bool:
    """Return True when *remote* is newer than *current*."""
    left = parse_version(remote)
    right = parse_version(current)
    size = max(len(left), len(right))
    for index in range(size):
        a = left[index] if index < len(left) else 0
        b = right[index] if index < len(right) else 0
        if a == b:
            continue
        if isinstance(a, int) and isinstance(b, int):
            return a > b
        return str(a) > str(b)
    return False
