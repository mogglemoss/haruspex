"""Help overlay screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

_HELP_TEXT = """\
[bold #C15F3C]HARUSPEX[/bold #C15F3C]  [#7a756e]keyboard reference[/#7a756e]

[#3a3530]── navigation ───────────────────────────[/#3a3530]
  [bold]d[/bold]        open D-Scan panel
  [bold]l[/bold]        open Local intel panel
  [bold]m[/bold]        open Monitoring panel
  [bold]Esc[/bold]      return to overview

[#3a3530]── d-scan ───────────────────────────────[/#3a3530]
  [bold]c[/bold]        copy scan summary to clipboard
  [bold]Ctrl+R[/bold]   clear scan input

[#3a3530]── local intel ──────────────────────────[/#3a3530]
  [bold]c[/bold]        copy intel summary to clipboard
  [italic]paste[/italic]    auto-triggers lookup after 600 ms

[#3a3530]── monitoring ───────────────────────────[/#3a3530]
  [bold]c[/bold]        copy intel summary to clipboard
  [bold]Ctrl+R[/bold]   clear pilot table
  [italic]click header[/italic]  sort by column

[#3a3530]── overview ─────────────────────────────[/#3a3530]
  [bold]c[/bold]        copy all panel intel at once
  [italic]click card[/italic]   open that panel full-screen

[#3a3530]── global ────────────────────────────────[/#3a3530]
  [bold]?[/bold]        show / close this help
  [bold]q[/bold]        quit

[#7a756e]HARUSPEX MAKES NO REPRESENTATIONS REGARDING
THE ACCURACY OF THIS HELP TEXT.[/#7a756e]\
"""


class HelpScreen(ModalScreen):
    """Modal help overlay."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("?", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    #help-box {
        width: 48;
        height: auto;
        background: #201d18;
        border: round #C15F3C;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(_HELP_TEXT, id="help-box")
