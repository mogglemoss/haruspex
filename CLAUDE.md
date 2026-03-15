# lazyscan

EVE Online D-scan and local intel TUI. Terminal-based, runs on a second monitor
alongside the game. Paste D-scan or local chat output, get instant threat analysis
and character intel. Optionally tail live log files for automatic enrichment.

## Stack

- **Language:** Python 3.11+
- **TUI framework:** Textual (https://textual.textualize.io)
- **HTTP:** httpx (async)
- **Package manager:** uv

## Project structure

```
lazyscan/
├── CLAUDE.md
├── pyproject.toml
├── README.md
├── lazyscan/
│   ├── __init__.py
│   ├── main.py          # Textual app entry point
│   ├── parsers/
│   │   ├── dscan.py     # D-scan text parser
│   │   ├── local.py     # Local chat roster parser
│   │   └── logs.py      # EVE log file tail/parser
│   ├── enrichers/
│   │   ├── sde.py       # Static Data Export ship lookups
│   │   ├── esi.py       # ESI API character/type resolution
│   │   └── zkill.py     # zKillboard kill stats
│   ├── ui/
│   │   ├── dscan_panel.py
│   │   ├── local_panel.py
│   │   └── log_panel.py
│   └── data/
│       └── ships.json   # Bundled SDE ship data (name → class/group)
└── tests/
    └── fixtures/        # Sample D-scan and local chat text for testing
```

## Phases

### Phase 1 — D-scan parser (offline, no network required)
- Parse raw D-scan clipboard text (tab-separated: distance, name, type)
- Ship class lookup against bundled ships.json (from EVE SDE)
- Summary: combat/recon/logi/hauler/structure/drone counts + percentages
- Notable hull flagging (Stratios, Loki, Sabre, Redeemer, combat recons, etc.)
- Threat assessment label (solo, small gang, fleet, structures only, etc.)
- Textual TUI with paste input pane + results pane
- Keybindings: [d] dscan mode, [l] local mode, [tab] switch panes, [q] quit

### Phase 2 — Local intel (requires network)
- Paste local chat roster (character names, one per line)
- ESI bulk name→ID resolution (/universe/ids/)
- zKillboard API stats per character (async, concurrent, rate-limited)
- Display: name, corp/alliance, kill count, loss count, last active, dangerous flag
- WH-aware: flag known wormhole corps and hunters
- WiNGSPAN Delivery Services corp/alliance recognition

### Phase 3 — Live log tail
- Watch ~/Documents/EVE/logs/Chatlogs/Local_*.txt in real time (UTF-16LE)
- Auto-trigger ESI+zKillboard lookup when new pilot appears in local

## Data sources

| Source | Usage | Auth |
|--------|-------|------|
| Bundled ships.json | Ship name → class/group lookup | None |
| ESI /universe/ids/ | Bulk name→ID resolution | None |
| ESI /universe/types/{id}/ | Ship type details | None |
| zKillboard API | Character kill stats | None |
| ~/Documents/EVE/logs/ | Live log tailing | Local file read |

## EVE log file details

- **Encoding:** UTF-16LE
- **macOS path:** `~/Documents/EVE/logs/Chatlogs/`
- **Linux (Steam+Proton):** `~/.local/share/Steam/steamapps/compatdata/8500/pfx/drive_c/users/steamuser/My Documents/EVE/logs/Chatlogs/`
- **Line format:** `[ YYYY.MM.DD HH:MM:SS ] CharacterName > message`
- **System messages:** sender is `EVE System`
- Reading log files is TOS-safe — CCP writes these files intentionally for
  third-party tools to consume. No cache scraping or network interception involved.

## TUI layout concept

```
┌─────────────────────────────────────────────────────────┐
│  lazyscan  │  [D] D-Scan  [L] Local  [G] Log  [H] Hist  │
├──────────────────┬──────────────────────────────────────┤
│  PASTE / INPUT   │  RESULTS                             │
│                  │                                      │
│  > ░             │  ⚔  Combat    12  [████████░░] 60%  │
│                  │  🔍 Recon      3  [███░░░░░░░] 15%  │
│                  │  ✚  Logi       2  [██░░░░░░░░] 10%  │
│                  │  📦 Other      3  [███░░░░░░░] 15%  │
│                  │                                      │
│                  │  ⚠ NOTABLE HULLS                     │
│                  │  Loki × 2   Huginn × 1  Sabre × 1   │
│                  │                                      │
│                  │  THREAT: HIGH — likely combat fleet  │
├──────────────────┴──────────────────────────────────────┤
│  [tab] switch pane  [c] copy  [↑↓] scroll  [q] quit     │
└─────────────────────────────────────────────────────────┘
```

## Key decisions

- **Textual over other TUI frameworks** — best Python TUI library, reactive,
  good async support, active development
- **uv for package management** — fast, modern, consistent with new projects
- **No login required for Phase 1 and 2** — ESI and zKillboard are public APIs
- **ships.json bundled** — avoid network dependency for core D-scan parsing;
  update script can refresh from SDE periodically
- **httpx async** — concurrent zKillboard lookups without blocking the TUI
- **UTF-16LE log reading** — EVE's non-standard encoding, must be explicit

## Notable ship classes to flag

Combat recons: Pilgrim, Curse, Huginn, Rapier, Lachesis, Arazu
Black ops: Redeemer, Sin, Widow, Panther
Heavy interdictors: Devoter, Onyx, Broadsword, Phobos
Interdictors: Sabre, Flycatcher, Heretic, Eris
Strategic cruisers: Loki, Tengu, Proteus, Legion
Covert ops / hunters: Stratios, Astero, Helios, Buzzard, Cheetah, Anathema, Imicus

## Developer context

- Developer: Scott (mogglemoss on GitHub)
- Related projects: ShortCircuit (EVE wormhole nav tool, Python/PyQt)
- EVE character: Cormorant Fell (WiNGSPAN alumni, wormhole space)
- Repo: github.com/mogglemoss/haruspex (create when ready)
- Build on MacBook (Cloud-Machine), run alongside EVE client

## Starting point

Begin with Phase 1. Steps:
1. Set up pyproject.toml with Textual + httpx dependencies via uv
2. Build ships.json from EVE SDE (Fuzzwork or static dump)
3. Implement dscan.py parser for raw clipboard text
4. Build basic Textual app with paste input + results display
5. Add ship class categorization and threat assessment logic
6. Add notable hull flagging
7. Wire up tests with fixture D-scan samples
