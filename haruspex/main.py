"""lazyscan — EVE Online D-scan and local intel TUI."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

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

    Header {
        background: $warm-surface;
        color: $rust;
        text-style: bold;
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
    """

    BINDINGS = [
        Binding("d", "switch_tab('dscan')", "D-Scan", show=True),
        Binding("l", "switch_tab('local')", "Local", show=True),
        Binding("g", "switch_tab('log')", "Log", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        self._config = Config.load()
        yield Header()
        with TabbedContent(initial="dscan"):
            with TabPane("D-Scan", id="dscan"):
                yield DscanPanel()
            with TabPane("Local", id="local"):
                yield LocalPanel()
            with TabPane("Log", id="log"):
                yield LogPanel(config=self._config)
        yield Footer()

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id


def main() -> None:
    LazyScanApp().run()


if __name__ == "__main__":
    main()
