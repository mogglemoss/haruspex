"""haruspex — EVE Online D-scan and local intel TUI."""
from __future__ import annotations

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer

from haruspex.ui.widgets import HaruspexHeader, PasteArea

from haruspex.config.settings import Config
from haruspex.ui.dscan_panel import DscanPanel
from haruspex.ui.help_screen import HelpScreen
from haruspex.ui.local_panel import LocalPanel
from haruspex.ui.log_panel import LogPanel


class LazyScanApp(App):
    """Main haruspex application."""

    TITLE = "HARUSPEX"
    SUB_TITLE = "Proximity Intelligence Platform · DSS-T3 · Capsuleer Edition"

    CSS = """
    /* ── Claude-inspired warm dark palette ── */
    $rust:        #C15F3C;
    $rust-dim:    #8A3820;
    $warm-bg:     #1a1815;
    $warm-surface:#201d18;
    $warm-panel:  #252118;
    $warm-text:   #e8e6e3;
    $warm-muted:  #7a756e;
    $warm-border: #3a3530;

    Screen {
        background: $warm-bg;
        color: $warm-text;
    }

    Footer {
        background: $warm-surface;
        color: $warm-muted;
    }

    #panels {
        height: 1fr;
    }

    /* Command palette */
    CommandPalette {
        background: $warm-surface;
    }
    CommandPalette > .command-palette--highlight {
        color: $rust;
        text-style: bold;
    }
    CommandPalette Input {
        background: $warm-panel;
        border: tall $warm-border;
        color: $warm-text;
    }
    CommandPalette Input:focus {
        border: tall $rust;
    }
    CommandPalette OptionList {
        background: $warm-surface;
        border: round $warm-border;
    }
    CommandPalette OptionList > .option-list--option-highlighted {
        background: $rust 20%;
        color: $warm-text;
    }
    CommandPalette OptionList > .option-list--option-hover {
        background: $warm-panel;
    }

    /* Kill the default blue focus ring and outline on every widget */
    *:focus {
        border: round $warm-border;
        outline: none;
    }

    /* DataTable — override all blue states globally.
       App CSS loads after DEFAULT_CSS so these win on equal specificity. */
    DataTable:focus {
        border: round $warm-border;
        outline: none;
    }

    DataTable > .datatable--cursor {
        background: $rust 25%;
        color: $warm-text;
    }

    DataTable > .datatable--hover {
        background: $rust 12%;
        color: $warm-text;
    }

    DataTable > .datatable--even-row {
        background: #1e1b16;
    }

    DataTable > .datatable--header {
        color: #a09890;
        background: $warm-surface;
    }

    /* Warm scrollbars — Textual defaults to blue */
    * {
        scrollbar-color: #5a5550;
        scrollbar-background: #1a1815;
        scrollbar-color-hover: $rust;
        scrollbar-background-hover: #1a1815;
        scrollbar-color-active: $rust;
        scrollbar-background-active: #1a1815;
    }

    /* PasteArea — suppress TextArea's blue cursor and selection */
    PasteArea > .text-area--cursor {
        background: $warm-border;
        color: $warm-text;
    }
    PasteArea > .text-area--selection {
        background: $warm-border 40%;
    }
    PasteArea:focus {
        border: round $warm-border;
    }
    """

    BINDINGS = [
        Binding("d", "focus_panel('dscan')", "D-Scan", show=True, priority=True),
        Binding("l", "focus_panel('local')", "Local", show=True, priority=True),
        Binding("m", "focus_panel('log')", "Monitoring", show=True, priority=True),
        Binding("escape", "exit_fullscreen", "Overview", show=True, priority=True),
        Binding("c", "copy_overview", "Copy intel", show=True, priority=True),
        Binding("question_mark", "show_help", "Help", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        self._config = Config.load()
        yield HaruspexHeader()
        with Horizontal(id="panels"):
            yield DscanPanel(id="panel-dscan")
            yield LocalPanel(config=self._config, id="panel-local")
            yield LogPanel(config=self._config, id="panel-log")
        yield Footer()

    def on_mount(self) -> None:
        self._fullscreen: str | None = None
        self._set_overview()

    def action_focus_panel(self, panel_id: str) -> None:
        if self._fullscreen == panel_id:
            self._set_overview()
        else:
            self._set_fullscreen(panel_id)

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "exit_fullscreen":
            return True if self._fullscreen else None  # None = hide from footer
        if action == "copy_overview":
            return None if self._fullscreen else True  # hide in detail (panels handle c)
        return True

    def action_exit_fullscreen(self) -> None:
        if self._fullscreen:
            self._set_overview()

    def action_copy_overview(self) -> None:
        parts = []
        for panel_id in ("dscan", "local", "log"):
            panel = self.query_one(f"#panel-{panel_id}")
            if hasattr(panel, "_copy_text"):
                text = panel._copy_text()
                if text:
                    parts.append(text)
        if parts:
            self.copy_to_clipboard("  ||  ".join(parts))

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def _set_fullscreen(self, panel_id: str) -> None:
        self._fullscreen = panel_id
        for child in self.query_one("#panels").children:
            if child.id == f"panel-{panel_id}":
                child.display = True
                child.set_mode("detail")
            else:
                child.display = False

    def _set_overview(self) -> None:
        self._fullscreen = None
        for child in self.query_one("#panels").children:
            child.display = True
            child.set_mode("overview")

    def on_paste(self, event: events.Paste) -> None:
        """Route paste to the active panel's input area (detail mode only)."""
        if not self._fullscreen:
            return
        target = {"dscan": "#paste-area", "local": "#local-paste-area"}.get(self._fullscreen)
        if target:
            self.query_one(target, PasteArea).load_text(event.text.strip())
            event.stop()


def main() -> None:
    LazyScanApp().run()


if __name__ == "__main__":
    main()
