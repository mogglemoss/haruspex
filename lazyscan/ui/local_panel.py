"""Local intel TUI panel."""
from __future__ import annotations

import asyncio
import re

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Label, Static, TextArea
from lazyscan.ui.widgets import PasteArea

from lazyscan.enrichers import esi, zkill
from lazyscan.parsers.local import parse

COLUMNS = ["Name", "Corp", "Alliance", "Kills", "Loss", "K/D", "Risk", "Tags"]


def _system_from_app(app: App) -> str:
    sub = app.sub_title
    if "·" in sub:
        return sub.split("·")[-1].strip()
    return ""


def _risk_val(risk_str: str) -> int:
    try:
        return int(risk_str.replace("%", "").strip())
    except ValueError:
        return 0


def _sort_key(col: int, row: tuple) -> object:
    v = row[col]
    if col in (3, 4):
        try: return int(v)
        except ValueError: return -1
    if col == 5:
        if v == "∞": return float("inf")
        try: return float(v)
        except ValueError: return -1.0
    if col == 6:
        if "HIGH" in v: return 999
        try: return int(v.replace("%", ""))
        except ValueError: return 0
    return re.sub(r"\[.*?\]", "", v).lower()


class LocalPanel(Static):
    """Local intel mode: paste roster → ESI + zKillboard lookup."""

    BINDINGS = [
        Binding("ctrl+g", "lookup", "Look up", show=False, priority=True),
        Binding("c", "copy_intel", "Copy intel", show=True),
    ]

    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    DEFAULT_CSS = """
    LocalPanel {
        layout: horizontal;
        height: 1fr;
        background: #1a1815;
    }

    #local-input-pane {
        width: 2fr;
        border: round #3a3530;
        padding: 1 2;
        margin: 1;
    }

    #local-results-pane {
        width: 5fr;
        border: round #3a3530;
        padding: 1 2;
        margin: 1;
    }

    #local-paste-area {
        height: 1fr;
        background: #252118;
        border: none;
        color: #e8e6e3;
    }

    #local-input-label {
        color: #7a756e;
        margin-bottom: 1;
    }

    #local-results-label {
        color: #C15F3C;
        text-style: bold;
        margin-bottom: 1;
    }

    #local-status {
        color: #7a756e;
        height: 1;
        margin-top: 1;
    }

    DataTable {
        height: 1fr;
        background: #1a1815;
    }

    DataTable > .datatable--header {
        color: #7a756e;
        background: #201d18;
    }

    DataTable > .datatable--cursor {
        background: #C15F3C 20%;
        color: #e8e6e3;
    }

    DataTable > .datatable--even-row {
        background: #1e1b16;
    }

    #local-empty-state {
        color: #7a756e;
        padding: 1 0;
    }
    """

    LOCAL_EMPTY = (
        "Deposit a personnel manifest in the left pane.\n"
        "HARUSPEX will resolve each name against the EVE registry "
        "and retrieve public kill records.\n\n"
        "[dim]TECHNICAL SPECIFICATIONS\n"
        "  Resolution engine  ESI /universe/ids/ · bulk name lookup\n"
        "  Kill data source   zKillboard public API\n"
        "  Request model      Async · rate-limited · 3 concurrent\n"
        "  Danger threshold   ≥50% danger ratio AND ≥10 kills\n"
        "  Auth required      No · public APIs only\n\n"
        "HARUSPEX PERSONNEL DIVISION DOES NOT GUARANTEE ACCURACY OF KILL DATA.\n\n"
        "PILOTS ABSENT FROM ZKILLBOARD WILL NOT BE FLAGGED. "
        "THIS IS A KNOWN LIMITATION AND NOT A BUG. "
        "THE DISTINCTION IS PHILOSOPHICAL.\n\n"
        "THE PERSON CURRENTLY SHOOTING YOU MAY OR MAY NOT APPEAR ON THIS LIST. "
        "HARUSPEX CONSIDERS THIS A MATTER BETWEEN YOU AND THEM.[/dim]"
    )

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="local-input-pane"):
                yield Label("deposit personnel manifest", id="local-input-label")
                yield PasteArea(id="local-paste-area", language=None)
                yield Static("", id="local-status")
            with Vertical(id="local-results-pane"):
                yield Label("personnel assessment", id="local-results-label")
                yield Static(self.LOCAL_EMPTY, id="local-empty-state")
                yield DataTable(id="local-table", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        self._rows: list[tuple] = []
        self._sort_col: int = 6   # default: Risk
        self._sort_asc: bool = False
        self._lookup_timer = None
        self._lookup_running: bool = False
        self._spin_task = None
        self._spin_i: int = 0
        table = self.query_one("#local-table", DataTable)
        table.add_columns(*COLUMNS)
        table.display = False

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Auto-trigger lookup 600ms after the paste settles."""
        if self._lookup_running:
            return
        if self._lookup_timer is not None:
            self._lookup_timer.stop()
        text = event.text_area.text.strip()
        if not text:
            return
        self._lookup_timer = self.set_timer(0.6, self._run_lookup)

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        col = event.column_index
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = col in (0, 1, 2, 7)
        self._render_rows()

    def action_lookup(self) -> None:
        self._run_lookup()

    def _run_lookup(self) -> None:
        if self._lookup_running:
            return
        text = self.query_one("#local-paste-area", TextArea).text
        names = parse(text)
        if not names:
            return
        self._lookup_running = True
        self._spin_task = asyncio.create_task(self._spinner(f"cross-referencing {len(names)} personnel"))
        asyncio.create_task(self._do_lookup(names))

    async def _spinner(self, msg: str) -> None:
        i = 0
        while True:
            ch = self.SPINNER[i % len(self.SPINNER)]
            self._set_status(f"[#C15F3C]{ch}[/#C15F3C]  {msg}")
            await asyncio.sleep(0.08)
            i += 1

    async def _do_lookup(self, names: list[str]) -> None:
        table = self.query_one("#local-table", DataTable)
        table.clear()
        label = self.query_one("#local-results-label", Label)
        label.update(f"consulting the registry · {len(names)} personnel...")

        try:
            char_infos = await esi.enrich_characters(names)
            char_ids = [c.character_id for c in char_infos if c.character_id]
            if self._spin_task:
                self._spin_task.cancel()
            self._spin_task = asyncio.create_task(self._spinner(f"reviewing incident histories · {len(char_ids)} personnel"))
            zkill_stats = await zkill.fetch_all(char_ids)

            rows = []
            for info in char_infos:
                zs = zkill_stats.get(info.character_id) if info.character_id else None

                kills = zs.kills if zs else 0
                losses = zs.losses if zs else 0
                kd = (
                    f"{kills/losses:.1f}" if (zs and kills > 0 and losses > 0)
                    else ("∞" if (zs and kills > 0) else "-")
                )
                danger_pct = zs.danger_ratio if zs else 0

                if zs and zs.dangerous:
                    danger = "[red]☠ HIGH[/red]"
                elif danger_pct >= 30:
                    danger = f"[yellow]{danger_pct}%[/yellow]"
                else:
                    danger = f"{danger_pct}%"

                tags: list[str] = []
                if zkill.is_wingspan(info.corp_name, info.alliance_name):
                    tags.append("[magenta]WINGSPAN[/magenta]")
                elif zkill.is_wh_corp(info.corp_name):
                    tags.append("[cyan]WH[/cyan]")
                elif zkill.is_wh_alliance(info.alliance_name):
                    tags.append("[cyan]WH[/cyan]")
                if zs and zs.error:
                    tags.append("[dim]no zkill[/dim]")

                corp_display = (
                    f"[{info.corp_ticker}] {info.corp_name}"
                    if info.corp_ticker
                    else info.corp_name or "?"
                )
                alliance_display = (
                    f"[{info.alliance_ticker}]"
                    if info.alliance_ticker
                    else info.alliance_name or "-"
                )

                rows.append((
                    info.name,
                    corp_display,
                    alliance_display,
                    str(kills),
                    str(losses),
                    kd,
                    danger,
                    " ".join(tags) if tags else "-",
                ))

            self._rows = rows
            self._render_rows()
            label.update(f"[#C15F3C]personnel assessment[/#C15F3C]  [dim]·[/dim]  [bold]{len(rows)}[/bold] [dim]on record[/dim]")
            self._set_status("")

        except Exception as e:
            label.update(f"[red]error: {e}[/red]")
            self._set_status("")
        finally:
            if self._spin_task:
                self._spin_task.cancel()
                self._spin_task = None
            self._lookup_running = False

    def _render_rows(self) -> None:
        table = self.query_one("#local-table", DataTable)
        empty = self.query_one("#local-empty-state", Static)
        table.clear()
        if self._rows:
            empty.display = False
            table.display = True
            col, asc = self._sort_col, self._sort_asc
            sorted_rows = sorted(self._rows, key=lambda r: _sort_key(col, r), reverse=not asc)
            for row in sorted_rows:
                table.add_row(*row)
        else:
            table.display = False
            empty.display = True

    def _set_status(self, msg: str) -> None:
        self.query_one("#local-status", Static).update(msg)

    def action_copy_intel(self) -> None:
        if not self._rows:
            return
        system = _system_from_app(self.app)
        flagged = [r for r in self._rows if "HIGH" in r[6] or ("%" in r[6] and _risk_val(r[6]) >= 30)]
        lines = [f"local{' · ' + system if system else ''} · {len(self._rows)} pilots"]
        if flagged:
            pilot_strs = []
            for r in flagged:
                name, _, _, kills, _, _, risk, tags = r
                tag_str = f" [{tags}]" if tags != "-" else ""
                pilot_strs.append(f"{name}{tag_str} {risk} {kills}k")
            lines.append("flagged: " + " · ".join(pilot_strs))
        else:
            lines.append("no flagged pilots")
        self.app.copy_to_clipboard("  |  ".join(lines))
