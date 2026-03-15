"""Live log tail panel — Phase 3."""
from __future__ import annotations

import asyncio
import re
from collections import OrderedDict
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Label, Static

from haruspex.config.settings import Config
from haruspex.enrichers import esi, zkill
from haruspex.parsers.logs import LogEvent, tail
from haruspex.ui.local_panel import _sort_key
from haruspex.ui.widgets import strip_markup

COLUMNS = ["Name", "Corp", "Alliance", "Kills", "Loss", "K/D", "Risk", "Tags"]


def _risk_val(risk_str: str) -> int:
    clean = re.sub(r"\[/?[^\[\]]*\]", "", risk_str)
    try:
        return int(clean.replace("%", "").strip())
    except ValueError:
        return 0


class LogPanel(Static):
    """Live local chat log tail with auto-enrichment."""

    BINDINGS = [
        Binding("ctrl+t", "toggle_tail", "Toggle tail", show=False, priority=True),
        Binding("c", "copy_intel", "Copy intel", show=True, priority=True),
        Binding("ctrl+r", "clear_table", "Clear", show=True),
    ]

    DEFAULT_CSS = """
    LogPanel {
        height: 1fr;
        width: 1fr;
        background: #1a1815;
    }

    LogPanel.overview {
        border: round #3a3530;
        padding: 1 2;
        margin: 1;
    }

    LogPanel.overview:hover {
        border: round #C15F3C;
    }

    #log-summary {
        height: 1fr;
        color: #e8e6e3;
    }

    #log-detail {
        height: 1fr;
    }

    #log-sidebar {
        width: 28;
        border: round #3a3530;
        padding: 1 2;
        margin: 1;
    }

    #log-results-pane {
        width: 1fr;
        border: round #3a3530;
        padding: 1 2;
        margin: 1;
    }

    #log-status-label {
        color: #7a756e;
        margin-bottom: 1;
    }

    #log-path-label {
        color: #7a756e;
        margin-top: 1;
    }

    #log-results-label {
        color: #C15F3C;
        text-style: bold;
        margin-bottom: 1;
    }

    DataTable {
        height: 1fr;
        background: #1a1815;
    }

    DataTable > .datatable--header {
        color: #a09890;
        background: #201d18;
    }

    DataTable > .datatable--cursor {
        background: #C15F3C 20%;
        color: #e8e6e3;
    }

    DataTable > .datatable--even-row {
        background: #1e1b16;
    }

    #enable-hint {
        color: #9a9590;
        margin-top: 2;
    }

    #log-empty-state {
        color: #9a9590;
        padding: 1 0;
    }
    """

    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    LOG_EMPTY = (
        "HARUSPEX is monitoring your local chat log.\n"
        "Pilots who speak in local will be enriched and added to this table.\n\n"
        "[dim]TECHNICAL SPECIFICATIONS\n"
        "  Monitoring method  Local chat log tail · UTF-16LE\n"
        "  Trigger event      Pilot speech in local channel\n"
        "  Coverage           All space types\n"
        "  Join detection     Not available · EVE does not log this\n"
        "  Poll interval      1 second\n\n"
        "HARUSPEX MONITORING DIVISION NOTES THAT SILENT LOCALS ARE NOT NECESSARILY SAFE LOCALS.\n\n"
        "PILOTS WHO DO NOT SPEAK WILL NOT APPEAR. "
        "HARUSPEX CONSIDERS THIS AN UPSTREAM LIMITATION.\n\n"
        "THIS SYSTEM DOES NOT DETECT CLOAKED HOSTILES. "
        "NO SYSTEM DOES. "
        "HARUSPEX RECOMMENDS TREATING ALL WORMHOLES AS OCCUPIED.[/dim]"
    )

    def __init__(self, config: Config, **kwargs):
        super().__init__(**kwargs)
        self._config = config
        self._tail_task: asyncio.Task | None = None
        self._spin_task: asyncio.Task | None = None
        self._enrich_queue: asyncio.Queue = asyncio.Queue()
        self._seen_pilots: OrderedDict[str, bool] = OrderedDict()  # name -> enriched
        self._rows: dict[str, tuple] = {}

    def compose(self) -> ComposeResult:
        yield Static("", id="log-summary")
        with Horizontal(id="log-detail"):
            with Vertical(id="log-sidebar"):
                yield Label("live monitoring", id="log-status-label")
                yield Static("", id="log-system-name")
                yield Static("", id="log-tail-status")
                yield Static("", id="log-path-label")
                yield Static("", id="enable-hint")
            with Vertical(id="log-results-pane"):
                yield Label("personnel assessment", id="log-results-label")
                yield Static(self.LOG_EMPTY, id="log-empty-state")
                yield DataTable(id="log-table", zebra_stripes=True, cursor_type="row")

    def on_click(self) -> None:
        if self.has_class("overview"):
            self.app.action_focus_panel("log")

    def on_resize(self) -> None:
        if self.has_class("overview"):
            self._refresh_summary()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        col = event.column_index
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = col in (0, 1, 2, 7)
        self._render_rows()

    def on_mount(self) -> None:
        self._rows: dict[str, tuple] = {}
        self._sort_col: int = 6   # default: Risk
        self._sort_asc: bool = False
        table = self.query_one("#log-table", DataTable)
        table.add_columns(*COLUMNS)
        table.display = False
        self.border_title = "[m] MONITORING"
        # Both hidden until set_mode is called by the app
        self.query_one("#log-summary").display = False
        self.query_one("#log-detail").display = False
        self._apply_config()

    def set_mode(self, mode: str) -> None:
        is_overview = mode == "overview"
        if is_overview:
            self.add_class("overview")
        else:
            self.remove_class("overview")
        self.query_one("#log-summary").display = is_overview
        self.query_one("#log-detail").display = not is_overview
        if is_overview:
            self._refresh_summary()

    def _refresh_summary(self) -> None:
        cfg = self._config.logs
        system = self._current_system()

        if not cfg.enabled:
            self.border_title = "[m] MONITORING"
            text = (
                "[#e8a559]MONITORING DISABLED.[/#e8a559]\n"
                "Log tailing is not enabled.\n\n"
                "[#7a756e]~/.config/lazyscan/config.toml[/#7a756e]"
            )
        elif not self._rows:
            self.border_title = "[m] MONITORING"
            system_line = f"\n[#C15F3C]{system}[/#C15F3C]" if system else ""
            text = (
                f"[#C15F3C]● MONITORING ACTIVE.[/#C15F3C]{system_line}\n\n"
                "No pilots have spoken.\n\n"
                "[#7a756e]Silent locals are not safe locals.[/#7a756e]"
            )
        else:
            count = len(self._rows)
            flagged = [
                r for r in self._rows.values()
                if "☠" in r[6] or ("%" in r[6] and _risk_val(r[6]) >= 30)
            ]
            if flagged:
                self.border_title = f"[m] MONITORING · {count}  [bold #ff6b6b]☠ {len(flagged)}[/bold #ff6b6b]"
            else:
                self.border_title = f"[m] MONITORING · {count}"
            header = f"[#C15F3C]● {system}[/#C15F3C]" if system else "[#C15F3C]● MONITORING ACTIVE.[/#C15F3C]"
            lines = [header, f"[bold]{count}[/bold] [#9a9590]pilots on record[/#9a9590]"]
            if flagged:
                lines.append(f"[bold #ff6b6b]{len(flagged)} flagged[/bold #ff6b6b]")
                lines.append("")

                h = self.size.height
                usable = (h - 4) if h > 8 else 999
                header_lines = len(lines)
                pilot_slots = usable - header_lines
                need_overflow = len(flagged) > pilot_slots
                if need_overflow:
                    pilot_slots -= 1

                for r in list(flagged)[:max(1, pilot_slots)]:
                    name = r[0]
                    risk = r[6]
                    kills = r[3]
                    tags = r[7]
                    tag_str = f"  [#7a756e]{strip_markup(tags)}[/#7a756e]" if tags != "-" else ""
                    if "☠" in risk:
                        lines.append(f"  [bold #ff6b6b]☠[/bold #ff6b6b] [bold]{name}[/bold]{tag_str}  [#7a756e]{kills} kills[/#7a756e]")
                    else:
                        pct = strip_markup(risk)
                        lines.append(f"  [bold]{name}[/bold]{tag_str}  [#e8a559]{pct} danger[/#e8a559]  [#7a756e]{kills} kills[/#7a756e]")

                remaining = len(flagged) - min(len(flagged), max(1, pilot_slots))
                if remaining > 0:
                    lines.append(f"  [#7a756e]… and {remaining} more[/#7a756e]")
            else:
                lines.append("[#7a756e]no flagged pilots[/#7a756e]")
            text = "\n".join(lines)

        self.query_one("#log-summary", Static).update(text)

    def _current_system(self) -> str:
        try:
            sub = self.app.sub_title
            if "·" in sub and "DSS-T3" not in sub:
                return sub.split("·")[-1].strip()
        except Exception:
            pass
        return ""

    def _apply_config(self) -> None:
        cfg = self._config.logs
        log_path = cfg.log_path

        if not cfg.enabled:
            self._show_setup(log_path)
            self._refresh_summary()
            return

        if log_path is None:
            self.query_one("#log-tail-status", Static).update(
                "[red]log directory not found[/red]"
            )
            self.query_one("#enable-hint", Static).update(
                "Specify log_path in\n[#7a756e]~/.config/lazyscan/config.toml[/#7a756e]"
            )
            self._refresh_summary()
            return

        self._start_tail(log_path)

    def _show_setup(self, detected: Path | None) -> None:
        from haruspex.config.settings import detect_log_path
        detected = detected or detect_log_path()

        self.query_one("#log-tail-status", Static).update("[#7a756e]standing by[/#7a756e]")
        if detected:
            self.query_one("#log-path-label", Static).update(
                f"[#7a756e]log directory located:[/#7a756e]\n{str(detected)[:26]}"
            )
            self.query_one("#enable-hint", Static).update(
                "HARUSPEX has located your EVE log directory "
                "but will not access it without explicit authorisation.\n\n"
                "LOG MONITORING IS APPROVED FOR CAPSULEER USE. "
                "CCP WRITES THESE FILES FOR THIRD-PARTY CONSUMPTION. "
                "HARUSPEX IS A THIRD PARTY.\n\n"
                "To enable, add to\n[#7a756e]~/.config/lazyscan/config.toml[/#7a756e]:\n\n"
                "[bold][logs]\nenabled = true[/bold]"
            )
        else:
            self.query_one("#enable-hint", Static).update(
                "No EVE log directory detected.\n\n"
                "Set path manually in\n[#7a756e]~/.config/lazyscan/config.toml[/#7a756e]"
            )

    def _start_tail(self, log_path: Path) -> None:
        short = str(log_path).replace(str(Path.home()), "~")
        self.query_one("#log-path-label", Static).update(f"[#7a756e]{short}[/#7a756e]")
        self.query_one("#log-tail-status", Static).update("[#C15F3C]● monitoring[/#C15F3C]")
        self._tail_task = asyncio.create_task(
            tail(log_path, self._on_log_event)
        )
        asyncio.create_task(self._enrich_worker())
        self._refresh_summary()

    def _update_system(self, system: str) -> None:
        # Clear stale intel from the previous system
        self._rows = {}
        self._seen_pilots.clear()
        self._render_rows()
        self.app.sub_title = f"Proximity Intelligence Platform  ·  {system}"
        self.query_one("#log-system-name", Static).update(f"[#C15F3C]{system}[/#C15F3C]")
        self._refresh_summary()

    async def _on_log_event(self, event: LogEvent) -> None:
        if event.system_changed:
            self._update_system(event.system_changed)
            return
        # Track anyone who speaks in local (EVE never logs join events — only chat)
        if event.is_system:
            return
        name = event.sender
        if name and name not in self._seen_pilots:
            self._seen_pilots[name] = False
            await self._enrich_queue.put(name)
            self._rows[name] = (name, "…", "-", "-", "-", "-", "-", "-")
            self._render_rows()

    async def _enrich_worker(self) -> None:
        """Consume the enrich queue and update rows as data arrives."""
        while True:
            name = await self._enrich_queue.get()
            try:
                self._spin_task = asyncio.create_task(
                    self._spinner(f"processing {name}")
                )
                char_infos = await esi.enrich_characters([name])
                char_ids = [c.character_id for c in char_infos if c.character_id]
                zkill_stats = await zkill.fetch_all(char_ids)

                for info in char_infos:
                    zs = zkill_stats.get(info.character_id) if info.character_id else None
                    self._rows[name] = self._build_row(info, zs)

                self._render_rows()
            except Exception as e:
                if name in self._rows:
                    self._rows[name] = (
                        name, f"[#5a5550]err: {type(e).__name__}[/#5a5550]",
                        "-", "-", "-", "-", "-", "-",
                    )
                self._render_rows()
            finally:
                if self._spin_task:
                    self._spin_task.cancel()
                    self._spin_task = None

    def _build_row(self, info, zs) -> tuple:
        from haruspex.enrichers.zkill import is_wingspan, is_wh_corp, is_wh_alliance

        kills = zs.kills if zs else 0
        losses = zs.losses if zs else 0
        kd = (
            f"{kills/losses:.1f}" if (zs and kills > 0 and losses > 0)
            else ("∞" if (zs and kills > 0) else "-")
        )
        danger_pct = zs.danger_ratio if zs else 0

        if zs and zs.dangerous:
            danger = "[bold red]☠[/bold red]"
        elif danger_pct >= 30:
            danger = f"[#e8a559]{danger_pct}%[/#e8a559]"
        else:
            danger = f"{danger_pct}%"

        extra_corps = set(self._config.logs.wh_corps) if self._config else None
        extra_alliances = set(self._config.logs.wh_alliances) if self._config else None
        tags: list[str] = []
        if is_wingspan(info.corp_name, info.alliance_name):
            tags.append("[#c47ab4]WINGSPAN[/#c47ab4]")
        elif is_wh_corp(info.corp_name, extra_corps):
            tags.append("[#4ec9c4]WH[/#4ec9c4]")
        elif is_wh_alliance(info.alliance_name, extra_alliances):
            tags.append("[#4ec9c4]WH[/#4ec9c4]")

        corp_display = (
            f"[{info.corp_ticker}] {info.corp_name}" if info.corp_ticker
            else info.corp_name or "?"
        )
        alliance_display = (
            f"[{info.alliance_ticker}]" if info.alliance_ticker
            else info.alliance_name or "-"
        )

        return (
            info.name, corp_display, alliance_display,
            str(kills), str(losses), kd, danger,
            " ".join(tags) if tags else "-",
        )

    def _render_rows(self) -> None:
        table = self.query_one("#log-table", DataTable)
        empty = self.query_one("#log-empty-state", Static)
        label = self.query_one("#log-results-label", Label)
        count = len(self._rows)
        table.clear()
        if self._rows:
            empty.display = False
            table.display = True
            label.update(
                f"[#C15F3C]personnel assessment[/#C15F3C]  [#3a3530]·[/#3a3530]  [bold]{count}[/bold] [#9a9590]on record[/#9a9590]"
            )
            col, asc = self._sort_col, self._sort_asc
            sorted_rows = sorted(self._rows.values(), key=lambda r: _sort_key(col, r), reverse=not asc)
            for row in sorted_rows:
                table.add_row(*row)
        else:
            table.display = False
            empty.display = True
            label.update("personnel assessment")
        self._refresh_summary()

    async def _spinner(self, msg: str) -> None:
        i = 0
        status = self.query_one("#log-tail-status", Static)
        while True:
            ch = self.SPINNER[i % len(self.SPINNER)]
            status.update(f"[#C15F3C]{ch}[/#C15F3C]  {msg}")
            await asyncio.sleep(0.08)
            i += 1

    def _copy_text(self) -> str | None:
        if not self._rows:
            return None
        system = self._current_system()
        flagged = [
            r for r in self._rows.values()
            if "☠" in r[6] or ("%" in r[6] and _risk_val(r[6]) >= 30)
        ]
        lines = [f"log{' · ' + system if system else ''} · {len(self._rows)} pilots"]
        if flagged:
            pilot_strs = []
            for r in flagged:
                name, _, _, kills, _, _, risk, tags = r
                tag_str = f" [{strip_markup(tags)}]" if tags != "-" else ""
                risk_clean = strip_markup(risk)
                risk_label = "☠" if "☠" in risk else f"{risk_clean} danger"
                pilot_strs.append(f"{name}{tag_str} {risk_label} {kills} kills")
            lines.append("flagged: " + " · ".join(pilot_strs))
        else:
            lines.append("no flagged pilots")
        return "  |  ".join(lines)

    def action_copy_intel(self) -> None:
        text = self._copy_text()
        if not text:
            return
        self.app.copy_to_clipboard(text)
        label = self.query_one("#log-results-label", Label)
        original = label.renderable
        label.update("[#7a756e]copied ✓[/#7a756e]")
        self.set_timer(2.0, lambda: label.update(original))

    def action_clear_table(self) -> None:
        self._rows = {}
        self._seen_pilots.clear()
        self._render_rows()

    def on_unmount(self) -> None:
        if self._tail_task:
            self._tail_task.cancel()
        if self._spin_task:
            self._spin_task.cancel()
