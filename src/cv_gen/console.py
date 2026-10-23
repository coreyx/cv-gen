"""Console setup so CV text prints on any terminal."""

from __future__ import annotations

import sys


def setup() -> None:
    """Make stdout and stderr write UTF-8, replacing what cannot be encoded.

    Windows consoles and pipes often default to a legacy code page (cp1252), on
    which an en dash in a date range or a bullet in scraped text raises
    ``UnicodeEncodeError`` mid-output.
    """
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding != "utf8" and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
