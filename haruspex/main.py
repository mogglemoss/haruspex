"""lazyscan — EVE Online D-scan and local intel TUI."""
from __future__ import annotations

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, TabbedContent, TabPane

from haruspex.ui.widgets import HaruspexHeader, PasteArea

from haruspex.config.settings import Config
from haruspex.ui.dscan_panel import DscanPanel
from haruspex.ui.local_panel import LocalPanel
from haruspex.ui.log_panel import LogPanel


class LazyScanApp(App):
    """Main lazyscan application."""

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

    TabbedContent {
        height: 1fr;
        background: $warm-bg;
    }

    TabPane {
        padding: 0;
        background: $warm-bg;
    }

    Tabs {
        background: $warm-surface;
        border-bottom: tall $warm-border;
    }

    Tab {
        color: $warm-muted;
        background: $warm-surface;
    }

    Tab:focus, Tab.-active {
        color: $rust;
        background: $warm-bg;
        text-style: bold;
    }

    Tab:hover {
        color: $warm-text;
        background: $warm-panel;
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

    /* Kill the default blue focus ring on every widget */
    *:focus {
        border: round $warm-border;
    }

    DataTable:focus {
        border: round $warm-border;
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
        Binding("d", "switch_tab('dscan')", "D-Scan", show=True, priority=True),
        Binding("l", "switch_tab('local')", "Local", show=True, priority=True),
        Binding("m", "switch_tab('log')", "Monitoring", show=True, priority=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        self._config = Config.load()
        yield HaruspexHeader()
        with TabbedContent(initial="dscan"):
            with TabPane("D-Scan", id="dscan"):
                yield DscanPanel()
            with TabPane("Local", id="local"):
                yield LocalPanel()
            with TabPane("Live Monitoring", id="log"):
                yield LogPanel(config=self._config)
        yield Footer()

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id

    def on_paste(self, event: events.Paste) -> None:
        """Route paste to the active tab's input area."""
        active = self.query_one(TabbedContent).active
        target = {"dscan": "#paste-area", "local": "#local-paste-area"}.get(active)
        if target:
            self.query_one(target, PasteArea).load_text(event.text.strip())
            event.stop()


def main() -> None:
    LazyScanApp().run()


if __name__ == "__main__":
    main()
