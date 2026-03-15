"""Local chat roster parser."""
from __future__ import annotations


def parse(text: str) -> list[str]:
    """Return a list of character names from a pasted local chat roster.

    Handles EVE's various copy formats:
    - Plain name-per-line (member list, basic copy)
    - Tab-separated  Name<TAB>Corp  (some client views)
    - Corp-header format (sorted-by-corp view includes corp name rows)
    - Chat conversation copy (timestamp + name > message — skipped)
    """
    names: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        # Tab-separated: take only the character name (first column)
        if "\t" in line:
            line = line.split("\t")[0]

        name = line.strip()
        if not name:
            continue

        # Skip known header/system strings
        if name.lower() in ("eve system", "local", "pilots in local"):
            continue

        # Skip EVE chat log lines: "[ YYYY.MM.DD HH:MM:SS ] ..."
        if name.startswith("[ ") and " ]" in name:
            continue

        # Skip plain timestamp blocks  [...]
        if name.startswith("[") and name.endswith("]"):
            continue

        # Skip chat messages: "Name > message text"
        if " > " in name:
            continue

        if name not in seen:
            seen.add(name)
            names.append(name)
    return names
