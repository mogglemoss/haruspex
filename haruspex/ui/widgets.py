"""Shared UI widgets."""
from __future__ import annotations

import re

from textual import events
from textual.widgets import TextArea

# Anglerfish mascot — lure glows in rust, eye in warm white, body in muted
MASCOT = (
    "      [#C15F3C]·[/#C15F3C]\n"
    "      [#C15F3C]│[/#C15F3C]\n"
    "  [#7a756e]╭───[/#7a756e][#C15F3C]●[/#C15F3C][#7a756e]──╮[/#7a756e]\n"
    " [#7a756e](│  [/#7a756e][#e8e6e3]◉[/#e8e6e3][#7a756e]   │)──[/#7a756e]\n"
    "  [#7a756e]╰───────╯[/#7a756e]\n"
    "  [dim]≈ ≈ ≈ ≈[/dim]"
)

_MARKUP_RE = re.compile(r"\[/?[^\[\]]*\]")


def strip_markup(text: str) -> str:
    """Remove Textual/Rich markup tags from a string."""
    return _MARKUP_RE.sub("", text)


class PasteArea(TextArea):
    """TextArea that replaces all content on paste instead of inserting.

    Textual calls every _on_paste handler in the MRO, so both this class's
    handler and TextArea's handler run. We load the new text first and set a
    flag; the overridden insert() discards the subsequent call from the parent
    handler so the text isn't doubled.
    """

    _suppress_next_insert: bool = False

    def _on_paste(self, event: events.Paste) -> None:
        self._suppress_next_insert = True
        self.load_text(event.text.strip())

    def insert(self, text: str, location=None, *, maintain_selection_offset: bool = True) -> None:
        if self._suppress_next_insert:
            self._suppress_next_insert = False
            return
        super().insert(text, location, maintain_selection_offset=maintain_selection_offset)
