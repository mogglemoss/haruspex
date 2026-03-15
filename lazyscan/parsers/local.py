"""Local chat roster parser."""
from __future__ import annotations


def parse(text: str) -> list[str]:
    """Return a list of character names from a pasted local chat roster.

    Handles both plain name-per-line and EVE's copy-from-chat format which
    may include timestamps or extra whitespace.
    """
    names: list[str] = []
    for line in text.splitlines():
        name = line.strip()
        if not name:
            continue
        # Skip obvious non-names (EVE System messages, headers)
        if name.lower() in ("eve system", "local", "pilots in local"):
            continue
        # Skip lines that look like timestamps [ YYYY.MM.DD ... ]
        if name.startswith("[") and name.endswith("]"):
            continue
        names.append(name)
    return names
