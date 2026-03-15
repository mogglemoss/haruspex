"""Shared UI widgets."""
from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, TextArea


# Full mascot — used on empty-state panels
MASCOT = (
    "      [#C15F3C]·[/#C15F3C]\n"
    "      [#C15F3C]│[/#C15F3C]\n"
    "  [#7a756e]╭───[/#7a756e][#C15F3C]●[/#C15F3C][#7a756e]──╮[/#7a756e]\n"
    " [#7a756e](│  [/#7a756e][#e8e6e3]◉[/#e8e6e3][#7a756e]   │)──[/#7a756e]\n"
    "  [#7a756e]╰───────╯[/#7a756e]\n"
    "  [#3a3530]≈ ≈ ≈ ≈[/#3a3530]"
)

_MARKUP_RE = re.compile(r"\[/?[^\[\]]*\]")


def strip_markup(text: str) -> str:
    """Remove Textual/Rich markup tags from a string."""
    return _MARKUP_RE.sub("", text)


# Esca bioluminescence cycle — slow pulse, brief flare, slow fade
_ESCA_FRAMES = [
    "#C15F3C",  # rest
    "#C15F3C",  # rest
    "#e8a559",  # flare
    "#C15F3C",  # rest
    "#8A3820",  # fade
    "#C15F3C",  # recover
]


def _mascot_header(esca_color: str) -> str:
    """Compact 3-line robot-head mascot.

    Antenna blinks (esca_color cycles). ( ) are ear-muffs on the face line,
    ╭──╮ is the top of the head, ◉ is the eye.

         ·          ← antenna tip       (pos 5)
     ╭───●───╮      ← head top + glow   (● at pos 5)
    (│   ◉   │)     ← face + ears       (◉ at pos 5)

    All lines left-aligned so positions are consistent.
    """
    return (
        f"     [bold {esca_color}]·[/bold {esca_color}]\n"
        f" [#7a756e]╭───[/#7a756e][{esca_color}]●[/{esca_color}][#7a756e]───╮[/#7a756e]\n"
        f"[#7a756e]([/#7a756e][#7a756e]│   [/#7a756e][#e8e6e3]◉[/#e8e6e3][#7a756e]   │)[/#7a756e]"
    )


class HaruspexHeader(Horizontal):
    """Persistent header with title, subtitle, and animated mascot."""

    DEFAULT_CSS = """
    HaruspexHeader {
        height: 3;
        background: #201d18;
        padding: 0 2;
        dock: top;
    }

    #header-titles {
        width: 1fr;
        height: 3;
    }

    #header-title {
        color: #C15F3C;
        text-style: bold;
        height: 1;
        content-align: left middle;
    }

    #header-subtitle {
        color: #7a756e;
        height: 1;
        content-align: left middle;
    }

    #header-system {
        height: 1;
        text-align: center;
        color: #C15F3C;
        text-style: bold;
    }

    #header-mascot {
        width: 13;
        height: 3;
        content-align: left top;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="header-titles"):
            yield Static("HARUSPEX", id="header-title")
            yield Static("", id="header-subtitle")
            yield Static("", id="header-system")
        yield Static(_mascot_header(_ESCA_FRAMES[0]), id="header-mascot")

    def on_mount(self) -> None:
        self._esca_frame = 0
        self._refresh_subtitle()
        self.watch(self.app, "sub_title", self._refresh_subtitle)
        self.set_interval(0.55, self._tick_esca)

    def _refresh_subtitle(self, value: str = "") -> None:
        sub = self.app.sub_title
        # Default subtitle contains "DSS-T3"; system-detected has one · separator
        if "DSS-T3" in sub or "·" not in sub:
            self.query_one("#header-subtitle", Static).update(sub)
            self.query_one("#header-system", Static).update("")
        else:
            platform, system = sub.rsplit("·", 1)
            self.query_one("#header-subtitle", Static).update(platform.strip())
            self.query_one("#header-system", Static).update(
                f"[bold #C15F3C]{system.strip().upper()}[/bold #C15F3C]"
            )

    def _tick_esca(self) -> None:
        self._esca_frame = (self._esca_frame + 1) % len(_ESCA_FRAMES)
        color = _ESCA_FRAMES[self._esca_frame]
        self.query_one("#header-mascot", Static).update(_mascot_header(color))


class PasteArea(TextArea):
    """Read-only paste target. Never takes keyboard focus.

    Content is loaded externally via load_text(). The widget exists only to
    display the pasted content — all key handling and paste routing happens
    at the app level.
    """

    can_focus = False

    def _on_paste(self, event) -> None:
        """Suppress all paste events — content is loaded externally."""
        event.stop()
