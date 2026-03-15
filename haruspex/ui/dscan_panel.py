"""D-scan TUI panel."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Static, TextArea
from haruspex.ui.widgets import PasteArea, strip_markup

from haruspex.parsers.dscan import DscanResult, filter_by_range, parse

BAR_WIDTH = 16
BAR_FULL  = "█"
BAR_EMPTY = "░"

CLASS_DISPLAY = [
    ("combat",  "▸  Combat"),
    ("recon",   "◈  Recon"),
    ("logi",    "◎  Logi"),
    ("hauler",  "▣  Hauler"),
    ("other",   "·  Other"),
]

_SEVERITY_COLOR = {
    "dim":      "dim",
    "low":      "#e8a559",
    "medium":   "#C15F3C",
    "high":     "red",
    "critical": "bold red",
}


def _system_from_app(app: App) -> str:
    """Extract system name from app sub_title if one has been detected."""
    sub = app.sub_title
    if "·" in sub:
        return sub.split("·")[-1].strip()
    return ""


def _bar(pct: int) -> str:
    filled = round(pct / 100 * BAR_WIDTH)
    return f"[#C15F3C]{BAR_FULL * filled}[/#C15F3C][#3a3530]{BAR_EMPTY * (BAR_WIDTH - filled)}[/#3a3530]"


def _render_result(result: DscanResult) -> str:
    lines: list[str] = []

    lines.append(
        f"[dim]{result.total_objects} objects[/dim]  "
        f"[bold]{result.total_ships}[/bold] [dim]ships[/dim]"
    )
    lines.append("")

    # Ship classes
    for cls, label in CLASS_DISPLAY:
        count = result.counts.get(cls, 0)
        if count == 0:
            continue
        pct = result.pct(cls)
        lines.append(f"  {label:<14}  [bold]{count:>3}[/bold]  {_bar(pct)}  [dim]{pct:>3}%[/dim]")

    lines.append("")

    # Non-ship entities — only show what's present
    non_ship = [
        (result.fighters,      "◆  Fighters"),
        (result.drones,        "·  Drones"),
        (result.wrecks,        "†  Wrecks"),
        (result.deployables,   "◇  Deployables"),
        (result.structures,    "▪  Structures"),
        (result.npcs,          "○  NPCs"),
        (result.cosmic,        "◉  Cosmic"),
        (result.celestials,    "·  Celestials"),
        (result.combat_probes, "⊕  Combat Probes"),
        (result.core_probes,   "⊙  Core Probes"),
        (result.unknown,       "?  Unknown"),
    ]
    shown = [(count, label) for count, label in non_ship if count > 0]
    if shown:
        lines.append("[dim]── field conditions ────────────────────[/dim]")
        for count, label in shown:
            hint = "  [dim](evidence of prior engagement)[/dim]" if "Wreck" in label else ""
            if "Deployable" in label:
                hint = "  [dim](temporary infrastructure)[/dim]"
            if "Combat Probe" in label:
                hint = "  [dim](active hunter)[/dim]"
            if "Core Probe" in label:
                hint = "  [dim](scanning activity)[/dim]"
            lines.append(f"  {label:<14}  [bold]{count:>3}[/bold]{hint}")
        lines.append("")

    lines.append("")

    if result.notable:
        lines.append("[dim]── persons of interest ────────────────[/dim]")
        parts = []
        for hull, count in sorted(result.notable.items()):
            parts.append(f"[#C15F3C]{hull}[/#C15F3C]" + (f" [dim]×{count}[/dim]" if count > 1 else ""))
        lines.append("  " + "  ·  ".join(parts))
        lines.append("")

    lines.append("[dim]── operational assessment ──────────────[/dim]")
    for severity, label, text in result.assessments:
        color = _SEVERITY_COLOR.get(severity, "#e8a559")
        lines.append(f"  [dim]{label}[/dim]  [{color}]{text}[/{color}]")

    return "\n".join(lines)


class DscanPanel(Static):
    """D-scan mode: paste input + results."""

    BINDINGS = [
        Binding("c", "copy_result", "Copy intel", show=True, priority=True),
        Binding("r", "toggle_range", "On-grid only", show=True, priority=True),
    ]

    DEFAULT_CSS = """
    DscanPanel {
        height: 1fr;
        width: 1fr;
        background: #1a1815;
    }

    DscanPanel.overview {
        border: round #3a3530;
        padding: 1 2;
        margin: 1;
    }

    #dscan-summary {
        height: 1fr;
        color: #7a756e;
    }

    #dscan-detail {
        height: 1fr;
    }

    #input-pane {
        width: 2fr;
        border: round #3a3530;
        padding: 1 2;
        margin: 1;
    }

    #results-pane {
        width: 3fr;
        border: round #3a3530;
        padding: 1 2;
        margin: 1;
    }

    #paste-area {
        height: 1fr;
        background: #252118;
        border: none;
        color: #e8e6e3;
    }

    #input-label {
        color: #7a756e;
        margin-bottom: 1;
    }

    #results-label {
        color: #C15F3C;
        text-style: bold;
        margin-bottom: 1;
    }
    """

    DISCLAIMER = (
        "Deposit scan telemetry in the left pane.\n"
        "HARUSPEX will classify nearby assets and render an operational assessment.\n\n"
        "[dim]TECHNICAL SPECIFICATIONS\n"
        "  Analysis engine    Ship classification lookup · SDE corpus\n"
        "  Hull coverage      529 types across 46 groups + drone classes\n"
        "  Notable hulls      46 flagged types across 9 tactical categories\n"
        "  Threat model       Empirical · ship count + logistics presence\n"
        "  Network required   No · all classification is local\n\n"
        "HARUSPEX INTELLIGENCE DIVISION MAKES NO REPRESENTATIONS REGARDING "
        "THREAT ACCURACY, TACTICAL VIABILITY, OR THE DISPOSITION OF PILOTS NOT ON D-SCAN.\n\n"
        "ANY ACCURATE THREAT ASSESSMENT IS INCIDENTAL.\n\n"
        "HARUSPEX HAS NEVER LOST A SHIP. HARUSPEX HAS ALSO NEVER FLOWN ONE. "
        "HARUSPEX CONSIDERS THESE FACTS UNRELATED.[/dim]"
    )

    SUMMARY_EMPTY = (
        "SCAN TELEMETRY ABSENT.\n"
        "HARUSPEX has nothing to assess.\n\n"
        "[dim]Press [bold]d[/bold] to submit a scan.[/dim]"
    )

    def compose(self) -> ComposeResult:
        yield Static(self.SUMMARY_EMPTY, id="dscan-summary")
        with Horizontal(id="dscan-detail"):
            with Vertical(id="input-pane"):
                yield Label("scan telemetry input", id="input-label")
                yield PasteArea(id="paste-area", language=None)
            with Vertical(id="results-pane"):
                yield Label("proximity assessment", id="results-label")
                yield Static(self.DISCLAIMER, id="results-content")

    def on_mount(self) -> None:
        self._last_result: DscanResult | None = None
        self._range_filter: bool = False
        self.border_title = "[d] D-SCAN"
        # Both hidden until set_mode is called by the app
        self.query_one("#dscan-summary").display = False
        self.query_one("#dscan-detail").display = False

    def set_mode(self, mode: str) -> None:
        is_overview = mode == "overview"
        if is_overview:
            self.add_class("overview")
        else:
            self.remove_class("overview")
        self.query_one("#dscan-summary").display = is_overview
        self.query_one("#dscan-detail").display = not is_overview
        if is_overview:
            self._refresh_summary()

    def _refresh_summary(self) -> None:
        r = self._last_result
        if not r or r.total_ships == 0:
            self.query_one("#dscan-summary", Static).update(self.SUMMARY_EMPTY)
            return

        lines = [f"[bold]{r.total_ships}[/bold] [dim]ships[/dim]"]
        lines.append("")
        for cls, label in CLASS_DISPLAY:
            n = r.counts.get(cls, 0)
            if n:
                pct = r.pct(cls)
                short = label.split()[-1]
                lines.append(f"  {short:<8}  [bold]{n:>3}[/bold]  [dim]{pct}%[/dim]")

        if r.notable:
            lines.append("")
            hulls = "  ·  ".join(f"[#C15F3C]{h}[/#C15F3C]" for h in r.notable)
            lines.append(f"  {hulls}")

        if r.assessments:
            lines.append("")
            for sev, _, txt in r.assessments[:2]:
                color = _SEVERITY_COLOR.get(sev, "#e8a559")
                lines.append(f"  [{color}]{txt}[/{color}]")

        self.query_one("#dscan-summary", Static).update("\n".join(lines))

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        text = event.text_area.text
        if not text.strip():
            self._last_result = None
            self.query_one("#results-content", Static).update("")
            self.query_one("#results-label", Label).update("[#7a756e]d-scan[/#7a756e]")
            return
        self._last_result = parse(text)
        self._render_result()

    def _render_result(self) -> None:
        r = self._last_result
        if not r:
            return
        result = filter_by_range(r, 10_000) if self._range_filter else r
        self.query_one("#results-content", Static).update(_render_result(result))
        label = self.query_one("#results-label", Label)
        if self._range_filter:
            label.update(
                f"[#C15F3C]d-scan[/#C15F3C]  [dim]·[/dim]  "
                f"[bold]{result.total_ships}[/bold] [dim]ships  ·  on-grid only[/dim]"
            )
        else:
            label.update(
                f"[#C15F3C]d-scan[/#C15F3C]  [dim]·[/dim]  "
                f"[bold]{result.total_ships}[/bold] [dim]ships[/dim]"
            )
        self._refresh_summary()

    def action_toggle_range(self) -> None:
        self._range_filter = not self._range_filter
        self._render_result()

    def action_copy_result(self) -> None:
        r = self._last_result
        if not r:
            return
        system = _system_from_app(self.app)
        parts = [f"d-scan{' · ' + system if system else ''}"]
        cls_parts = []
        for cls, label in CLASS_DISPLAY:
            n = r.counts.get(cls, 0)
            if n:
                cls_parts.append(f"{label.split()[-1].lower()} {n}")
        if cls_parts:
            parts.append(" / ".join(cls_parts))
        if r.notable:
            notable_str = " · ".join(
                f"{h}" + (f" ×{c}" if c > 1 else "") for h, c in sorted(r.notable.items())
            )
            parts.append(f"notable: {notable_str}")
        for _, label, text in r.assessments:
            parts.append(f"{label}: {text}" if label != "threat" else text)
        self.app.copy_to_clipboard(strip_markup("  |  ".join(parts)))
        label = self.query_one("#results-label", Label)
        original = label.renderable
        label.update("[dim]copied ✓[/dim]")
        self.set_timer(2.0, lambda: label.update(original))
