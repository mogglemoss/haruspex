"""Local intel TUI panel."""
from __future__ import annotations

import asyncio
import re

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Label, Static, TextArea
from haruspex.ui.widgets import PasteArea, strip_markup

from haruspex.enrichers import esi, zkill
from haruspex.parsers.local import parse

COLUMNS = ["Name", "Corp", "Alliance", "Kills", "Loss", "K/D", "Risk", "Tags"]

# Session cache: character name → rendered row tuple (persists for app lifetime)
_SESSION_CACHE: dict[str, tuple] = {}


def _system_from_app(app: App) -> str:
    sub = app.sub_title
    if "·" in sub:
        return sub.split("·")[-1].strip()
    return ""


def _risk_val(risk_str: str) -> int:
    clean = re.sub(r"\[/?[^\[\]]*\]", "", risk_str)
    try:
        return int(clean.replace("%", "").strip())
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
        if "☠" in v: return 999
        clean = re.sub(r"\[/?[^\[\]]*\]", "", v)
        try: return int(clean.replace("%", "").strip())
        except ValueError: return 0
    return re.sub(r"\[.*?\]", "", v).lower()


class LocalPanel(Static):
    """Local intel mode: paste roster → ESI + zKillboard lookup."""

    BINDINGS = [
        Binding("ctrl+g", "lookup", "Look up", show=False, priority=True),
        Binding("c", "copy_intel", "Copy intel", show=True, priority=True),
    ]

    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    DEFAULT_CSS = """
    LocalPanel {
        height: 1fr;
        width: 1fr;
        background: #1a1815;
    }

    LocalPanel.overview {
        border: round #3a3530;
        padding: 1 2;
        margin: 1;
    }

    LocalPanel.overview:hover {
        border: round #C15F3C;
    }

    #local-summary {
        height: 1fr;
        color: #7a756e;
    }

    #local-detail {
        height: 1fr;
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

    SUMMARY_EMPTY = (
        "NO PERSONNEL ON FILE.\n"
        "HARUSPEX has no one to look up.\n\n"
        "[dim]Press [bold]l[/bold] to deposit a roster.[/dim]"
    )

    def compose(self) -> ComposeResult:
        yield Static(self.SUMMARY_EMPTY, id="local-summary")
        with Horizontal(id="local-detail"):
            with Vertical(id="local-input-pane"):
                yield Label("deposit personnel manifest", id="local-input-label")
                yield PasteArea(id="local-paste-area", language=None)
                yield Static("", id="local-status")
            with Vertical(id="local-results-pane"):
                yield Label("personnel assessment", id="local-results-label")
                yield Static(self.LOCAL_EMPTY, id="local-empty-state")
                yield DataTable(id="local-table", zebra_stripes=True, cursor_type="row")

    def on_click(self) -> None:
        if self.has_class("overview"):
            self.app.action_focus_panel("local")

    def on_resize(self) -> None:
        if self.has_class("overview"):
            self._refresh_summary()

    def on_mount(self) -> None:
        self._rows: list[tuple] = []
        self._sort_col: int = 6   # default: Risk
        self._sort_asc: bool = False
        self._lookup_timer = None
        self._lookup_running: bool = False
        self._lookup_count: int = 0
        self._spin_task = None
        self._spin_i: int = 0
        table = self.query_one("#local-table", DataTable)
        table.add_columns(*COLUMNS)
        table.display = False
        self.border_title = "[l] LOCAL"
        # Both hidden until set_mode is called by the app
        self.query_one("#local-summary").display = False
        self.query_one("#local-detail").display = False

    def set_mode(self, mode: str) -> None:
        is_overview = mode == "overview"
        if is_overview:
            self.add_class("overview")
        else:
            self.remove_class("overview")
        self.query_one("#local-summary").display = is_overview
        self.query_one("#local-detail").display = not is_overview
        if is_overview:
            self._refresh_summary()

    def _refresh_summary(self) -> None:
        if self._lookup_running:
            self.border_title = f"[l] LOCAL · [#e8a559]scanning {self._lookup_count}[/#e8a559]"
            text = (
                f"[#e8a559]ASSESSMENT IN PROGRESS.[/#e8a559]\n"
                f"HARUSPEX is cross-referencing "
                f"[bold]{self._lookup_count}[/bold] personnel.\n\n"
                "[#7a756e]Consulting the registry.\n"
                "Stand by.[/#7a756e]"
            )
            self.query_one("#local-summary", Static).update(text)
            return

        if not self._rows:
            self.border_title = "[l] LOCAL"
            self.query_one("#local-summary", Static).update(self.SUMMARY_EMPTY)
            return

        count = len(self._rows)
        flagged = [r for r in self._rows if "☠" in r[6] or ("%" in r[6] and _risk_val(r[6]) >= 30)]
        if flagged:
            self.border_title = f"[l] LOCAL · {count}  [bold #ff6b6b]☠ {len(flagged)}[/bold #ff6b6b]"
        else:
            self.border_title = f"[l] LOCAL · {count}"
        lines = [f"[bold]{count}[/bold] [#9a9590]pilots on record[/#9a9590]"]

        if flagged:
            lines.append(f"[bold #ff6b6b]{len(flagged)} flagged[/bold #ff6b6b]")
            lines.append("")

            # Dynamically fill available vertical space.
            # self.size.height is outer height; subtract border (2) + padding (2).
            # Header above pilot list = lines so far (count + flagged + blank = 3).
            # Fall back to large number when not yet laid out (size = 0).
            h = self.size.height
            usable = (h - 4) if h > 8 else 999
            header_lines = len(lines)  # lines emitted so far
            pilot_slots = usable - header_lines
            need_overflow = len(flagged) > pilot_slots
            if need_overflow:
                pilot_slots -= 1  # reserve one line for the overflow indicator

            for r in flagged[:max(1, pilot_slots)]:
                name, _, _, kills, _, _, risk, tags = r
                tag_str = f"  [{strip_markup(tags)}]" if tags != "-" else ""
                lines.append(f"  [bold]{name}[/bold]{tag_str}  {risk}  [#7a756e]{kills}k[/#7a756e]")

            remaining = len(flagged) - min(len(flagged), max(1, pilot_slots))
            if remaining > 0:
                lines.append(f"  [#7a756e]… and {remaining} more[/#7a756e]")
        else:
            lines.append("[#7a756e]no flagged pilots[/#7a756e]")

        self.query_one("#local-summary", Static).update("\n".join(lines))

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
        self._lookup_count = len(names)
        self._refresh_summary()
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

        cached_rows = [_SESSION_CACHE[n] for n in names if n in _SESSION_CACHE]
        uncached = [n for n in names if n not in _SESSION_CACHE]

        label.update(
            f"consulting the registry · {len(uncached)} new · {len(cached_rows)} cached..."
            if cached_rows else f"consulting the registry · {len(uncached)} personnel..."
        )

        try:
            rows = list(cached_rows)

            if uncached:
                char_infos = await esi.enrich_characters(uncached)
                char_ids = [c.character_id for c in char_infos if c.character_id]
                if self._spin_task:
                    self._spin_task.cancel()
                self._spin_task = asyncio.create_task(self._spinner(f"reviewing incident histories · {len(char_ids)} personnel"))
                zkill_stats = await zkill.fetch_all(char_ids)
            else:
                char_infos = []
                zkill_stats = {}
                if self._spin_task:
                    self._spin_task.cancel()
                    self._spin_task = None

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
                    danger = "[bold red]☠[/bold red]"
                elif danger_pct >= 30:
                    danger = f"[#e8a559]{danger_pct}%[/#e8a559]"
                else:
                    danger = f"{danger_pct}%"

                tags: list[str] = []
                if zkill.is_wingspan(info.corp_name, info.alliance_name):
                    tags.append("[#c47ab4]WINGSPAN[/#c47ab4]")
                elif zkill.is_wh_corp(info.corp_name):
                    tags.append("[#4ec9c4]WH[/#4ec9c4]")
                elif zkill.is_wh_alliance(info.alliance_name):
                    tags.append("[#4ec9c4]WH[/#4ec9c4]")
                if zs and zs.error:
                    tags.append("[#5a5550]no zkill[/#5a5550]")

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

                row = (
                    info.name,
                    corp_display,
                    alliance_display,
                    str(kills),
                    str(losses),
                    kd,
                    danger,
                    " ".join(tags) if tags else "-",
                )
                _SESSION_CACHE[info.name] = row
                rows.append(row)

            self._rows = rows
            self._render_rows()
            label.update(f"[#C15F3C]personnel assessment[/#C15F3C]  [#3a3530]·[/#3a3530]  [bold]{len(rows)}[/bold] [#9a9590]on record[/#9a9590]")
            self._set_status("")
            self._refresh_summary()

        except Exception as e:
            label.update(f"[red]error: {e}[/red]")
            self._set_status("")
        finally:
            if self._spin_task:
                self._spin_task.cancel()
                self._spin_task = None
            self._lookup_running = False
            self._refresh_summary()

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
        flagged = [r for r in self._rows if "☠" in r[6] or ("%" in r[6] and _risk_val(r[6]) >= 30)]
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
        self.app.copy_to_clipboard(strip_markup("  |  ".join(lines)))
        self._set_status("[#7a756e]copied ✓[/#7a756e]")
        self.set_timer(2.0, lambda: self._set_status(""))
