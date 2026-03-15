# HARUSPEX

**Proximity Intelligence Platform · DSS-T3 · Capsuleer Edition**

A terminal-based EVE Online intel tool. Runs on a second monitor alongside the game. Paste D-scan output or local chat rosters for instant threat assessment and character intel. Optionally tails your EVE chat logs for live enrichment of pilots who speak in local.

```
HARUSPEX INTELLIGENCE DIVISION MAKES NO REPRESENTATIONS REGARDING
THREAT ACCURACY, TACTICAL VIABILITY, OR THE DISPOSITION OF PILOTS NOT ON D-SCAN.

HARUSPEX HAS NEVER LOST A SHIP. HARUSPEX HAS ALSO NEVER FLOWN ONE.
HARUSPEX CONSIDERS THESE FACTS UNRELATED.
```

---

## Features

**D-Scan** — paste raw directional scan output, get instant ship classification, threat assessment, and notable hull flagging. Press `r` to filter to on-grid only (<10,000 km).

**Local** — paste your local chat roster, HARUSPEX resolves each name via ESI and retrieves kill records from zKillboard. Sortable by any column. Results cached for the session.

**Log** — if enabled, watches your EVE chat logs in real time. Any pilot who speaks in local is automatically enriched and added to the table. System name appears in the header.

---

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/mogglemoss/haruspex
cd haruspex
uv sync
uv run haruspex
```

---

## Configuration

HARUSPEX works out of the box for D-scan and Local. Live log tailing is opt-in.

Create `~/.config/haruspex/config.toml`:

```toml
[logs]
enabled = true
```

HARUSPEX will auto-detect your EVE log directory on macOS and Linux (Steam/Proton). To set a custom path:

```toml
[logs]
enabled = true
path = "~/Documents/EVE/logs/Chatlogs"
```

**Log monitoring is TOS-compliant.** CCP writes these files for third-party tool consumption. HARUSPEX is a third party.

---

## Keybindings

| Key | Action |
|-----|--------|
| `d` | Switch to D-Scan tab |
| `l` | Switch to Local tab |
| `g` | Switch to Log tab |
| `c` | Copy intel summary to clipboard |
| `r` | D-Scan: toggle on-grid filter (<10,000 km) |
| `ctrl+r` | Log: clear table |
| `q` | Quit |

---

## Technical Specifications

| Component | Detail |
|-----------|--------|
| Analysis engine | Ship classification · SDE corpus |
| Hull coverage | 529 types · 46 groups · drone classes |
| Notable hulls | 46 flagged types · 9 tactical categories |
| Name resolution | ESI `/universe/ids/` · bulk |
| Kill data | zKillboard public API · rate-limited |
| Danger threshold | ≥50% danger ratio AND ≥10 kills |
| Log format | UTF-16LE · 1s poll interval |
| Auth required | None · public APIs only |

---

## Data Sources

| Source | Purpose | Auth |
|--------|---------|------|
| Bundled `ships.json` | Ship name → class/group | None |
| ESI `/universe/ids/` | Bulk name → ID resolution | None |
| ESI `/characters/{id}/` | Corp and alliance details | None |
| zKillboard API | Character kill statistics | None |
| `~/Documents/EVE/logs/` | Live chat log tailing | Local read |

---

## Platform Support

- **macOS** — auto-detected log path
- **Linux (Steam/Proton)** — auto-detected
- **Linux (Steam Flatpak)** — auto-detected
- **Windows** — set path manually in config

---

## License

MIT — see LICENSE

---

*Built with [Textual](https://textual.textualize.io). A [Deep Sea Sleeper](https://deepseasleeper.com) project.*
