# HARUSPEX

EVE Online D-scan and local intel TUI. Terminal-based, runs on a second monitor
alongside the game. Paste D-scan or local chat output for instant threat analysis
and character intel. Optionally tail live log files for automatic enrichment.

## Stack

- **Language:** Python 3.11+
- **TUI framework:** Textual (https://textual.textualize.io)
- **HTTP:** httpx (async)
- **Package manager:** uv
- **Distribution:** PyInstaller (single-file binaries via GitHub Actions)

## Project structure

```
haruspex/                        ← repo root (local folder may differ)
├── CLAUDE.md
├── pyproject.toml
├── README.md
├── haruspex.spec                # PyInstaller build spec
├── .github/
│   └── workflows/
│       └── build.yml            # Matrix build: Linux, Windows, macOS universal
├── haruspex/
│   ├── __init__.py
│   ├── main.py                  # Textual app entry point (LazyScanApp)
│   ├── config/
│   │   └── settings.py          # Config dataclass, TOML load/save
│   ├── parsers/
│   │   ├── dscan.py             # D-scan clipboard parser
│   │   ├── local.py             # Local chat roster parser
│   │   └── logs.py              # EVE chatlog tail/parser (UTF-16LE)
│   ├── enrichers/
│   │   ├── esi.py               # ESI character/corp/alliance resolution
│   │   └── zkill.py             # zKillboard kill stats + WH corp detection
│   ├── ui/
│   │   ├── widgets.py           # HaruspexHeader, PasteArea, mascot animation
│   │   ├── dscan_panel.py       # D-scan panel
│   │   ├── local_panel.py       # Local intel panel
│   │   ├── log_panel.py         # Live monitoring panel
│   │   └── help_screen.py       # ? help overlay (ModalScreen)
│   └── data/
│       └── ships.json           # Bundled SDE ship data (name → class/group)
└── tests/
    └── fixtures/                # Sample D-scan and local chat text
```

## Layout

btop-style overview / fullscreen. All three panels visible in overview as cards;
pressing `d`, `l`, or `m` expands that panel to fullscreen. `Esc` returns to overview.

Each panel has two modes:
- **overview** — compact summary card with border, click to expand
- **detail** — full input + results layout

`main.py` tracks `_fullscreen: str | None` and calls `panel.set_mode("overview"|"detail")`.
`check_action` hides `Esc` from the footer when already in overview, hides the app-level
`c` (copy overview) when in detail mode (panels own `c` in detail).

## Keybindings

| Key | Action |
|-----|--------|
| `d` / `l` / `m` | Open D-Scan / Local / Monitoring panel |
| `Esc` | Return to overview |
| `c` | Copy intel (overview: all panels combined; detail: current panel) |
| `?` | Help overlay |
| `Ctrl+R` | Clear current panel |
| `q` | Quit |

## Configuration (`~/.config/lazyscan/config.toml`)

```toml
[logs]
enabled = true
path = ""                        # optional override; auto-detected if blank
wh_corps = []                    # extra WH corp name fragments (case-insensitive)
wh_alliances = []                # extra WH alliance name fragments
```

Log monitoring is opt-in. Auto-detection covers macOS, Linux native, Steam/Proton,
and Steam Flatpak paths. `wh_corps`/`wh_alliances` extend (not replace) the built-in
lists in `zkill.py`.

## Key decisions

- **Textual** — best Python TUI library, reactive, good async support
- **uv** — fast, modern package management
- **btop-style layout** — overview cards + fullscreen detail, no tabs
- **No D-scan range filter** — user controls scan range in EVE directly; not our concern
- **ships.json bundled** — zero network dependency for D-scan; update script in scripts/
- **httpx async** — concurrent zKillboard lookups without blocking TUI
- **UTF-16LE log reading** — EVE's non-standard encoding, must be explicit
- **PyInstaller --onefile** — single executable, no Python required for end users
- **macOS universal binary** — build x64 (macos-13) and arm64 (macos-latest) separately,
  combine with `lipo`; triggered on version tags via GitHub Actions
- **No combat log / intel channel parsing** — out of scope

## Notable ship classes flagged

Combat recons: Pilgrim, Curse, Huginn, Rapier, Lachesis, Arazu
Black ops: Redeemer, Sin, Widow, Panther
Heavy interdictors: Devoter, Onyx, Broadsword, Phobos
Interdictors: Sabre, Flycatcher, Heretic, Eris
Strategic cruisers: Loki, Tengu, Proteus, Legion
Covert ops / hunters: Stratios, Astero, Helios, Buzzard, Cheetah, Anathema, Imicus

## Data sources

| Source | Usage | Auth |
|--------|-------|------|
| Bundled ships.json | Ship name → class/group lookup | None |
| ESI /universe/ids/ | Bulk name→ID resolution | None |
| ESI /characters/{id}/ | Corp and alliance details | None |
| zKillboard API | Character kill stats | None |
| ~/Documents/EVE/logs/ | Live log tailing | Local file read |

## EVE log file details

- **Encoding:** UTF-16LE
- **macOS path:** `~/Documents/EVE/logs/Chatlogs/`
- **Linux Steam/Proton:** `~/.local/share/Steam/steamapps/compatdata/8500/pfx/drive_c/users/steamuser/My Documents/EVE/logs/Chatlogs/`
- **Line format:** `[ YYYY.MM.DD HH:MM:SS ] CharacterName > message`
- **System messages:** sender is `EVE System`
- Reading log files is TOS-safe — CCP writes these files for third-party consumption.

## Developer context

- Developer: Scott (mogglemoss on GitHub)
- Related projects: ShortCircuit (EVE wormhole nav tool, Python/PyQt)
- EVE character: Cormorant Fell (WiNGSPAN alumni, wormhole space)
- Repo: github.com/mogglemoss/haruspex
- Build on MacBook, run alongside EVE client
- v1.0.0 shipped — all three phases complete
