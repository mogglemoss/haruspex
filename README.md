# HARUSPEX

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/mogglemoss/haruspex)](https://github.com/mogglemoss/haruspex/releases)
[![Build Status](https://github.com/mogglemoss/haruspex/actions/workflows/build.yml/badge.svg)](https://github.com/mogglemoss/haruspex/actions/workflows/build.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-C15F3C)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-3a3530)](LICENSE)

<img src="assets/cormorantfell-portrait.jpeg" width="72" align="right">

> [Cormorant Fell](https://evewho.com/character/93594488) — WiNGSPAN alumni and, on balance, more of a wormhole enthusiast than a wormhole survivor — built this. It works. It has opinions. Some of them are correct.

**Proximity Intelligence Platform · DSS-T3 · Capsuleer Edition**

HARUSPEX is a terminal-based EVE Online intel tool. Run it on a second monitor, alt-tab to it, prop it in a corner — HARUSPEX has no opinion on your window management and is not your Space Mom. You paste things into it. It tells you things about those things. Whether those things are accurate is, per HARUSPEX's own legal counsel, a matter of active philosophical inquiry.

```
HARUSPEX INTELLIGENCE DIVISION MAKES NO REPRESENTATIONS REGARDING
THREAT ACCURACY, TACTICAL VIABILITY, OR THE DISPOSITION OF PILOTS
NOT ON D-SCAN.

HARUSPEX HAS NEVER LOST A SHIP.
HARUSPEX HAS ALSO NEVER FLOWN ONE.
HARUSPEX CONSIDERS THESE FACTS UNRELATED.
```

---

![HARUSPEX overview — D-Scan, Local, and Monitoring panels](assets/haruspex.png)

---

## What It Does

**D-Scan** ingests the raw output of your directional scanner and returns a structured tactical picture. This happens locally, against a bundled ship database covering 529 hull types, in under a millisecond. No network request is made. The results are therefore equally fast whether you are in Jita or a C5 with no static.

Ships are classified into five tactical categories — **▸ Combat, ◆ Recon, ◎ Logi, ○ Hauler, · Other** — each rendered with a proportional bar chart and percentage breakdown. This is the part that tells you roughly what kind of problem you have.

**Signals of Interest** identifies tactically significant hulls and groups them by category in threat-priority order: Black Ops, Command Ships, Heavy Interdictors, Interdictors, Combat Recons, Strategic Cruisers, Logistics Battleships, and the covert-capable classes. Each category is iconised for rapid scanning. This is the part that tells you specifically what kind of problem you have.

Combat Recon Ships carry a passive role bonus reducing their sensor strength to zero, making them invisible to directional scanners by design. If one nonetheless appears in Signals of Interest, HARUSPEX notes this and considers it significant. HARUSPEX does not speculate as to how.

**Field conditions** catalogues everything that is not a ship, with annotations where context changes the meaning:

- A **Mobile Tractor Unit** indicates a pilot currently running a site. They are probably not watching their directional scanner. HARUSPEX considers this tactically relevant.
- A **deployed warp disruption probe** indicates something is being caught right now.
- A **cynosural field** indicates that whatever was invited has arrived.
- **Combat probes** indicate an active hunter. You may be the target. HARUSPEX cannot confirm this but thinks it worth mentioning.
- A **MTU alongside wrecks** resolves to a more specific annotation than either alone.

The **operational assessment** synthesises the above: fleet archetype (gate camp, wormhole hunter gang, doctrine fleet, doctrine fleet with ewar wing, black ops drop, capital escalation, nano roam, and others), logistics ratio when it crosses significance thresholds, and an overall threat statement. It is produced by an analyst who has reached these conclusions before and finds them only mildly interesting.

The **overview card** presents a compressed version of the full analysis — bar chart, signals of interest by category, field condition flags, and all assessment lines — so the picture is legible at a glance before you commit to opening the panel. Pressing `d` opens the full assessment. Pressing `Esc` returns you to the overview, where HARUSPEX will continue to hold your results without complaint.

---

**Local** accepts a paste of your local chat roster and cross-references every name against the EVE registry and zKillboard's public kill records. It will tell you how many people have died, how dangerous they are assessed to be, and whether any of them are known wormhole affiliates. It will not tell you whether any of them are about to kill you. That information is available elsewhere, typically in the form of a bright flash and a pod notification.

---

**Monitoring** watches your EVE chat logs in real time. Any pilot who speaks in local is automatically enriched, assessed, and added to the table without further input from you. The system name is detected automatically and displayed in the header. Pilots who do not speak will not appear. HARUSPEX considers this an upstream limitation and has filed the appropriate documentation.

---

## Installation

Pre-compiled binaries are available on the [Releases page](https://github.com/mogglemoss/haruspex/releases) for macOS (universal), Linux, and Windows. No Python required. No assembly required. No explanation of what a wormhole is required.

### macOS

Download `haruspex-macos`, then in Terminal:

```bash
chmod +x ~/Downloads/haruspex-macos
xattr -d com.apple.quarantine ~/Downloads/haruspex-macos
~/Downloads/haruspex-macos
```

`chmod` grants execute permission (required after download). `xattr` clears the Gatekeeper quarantine flag — macOS applies this to all downloaded files; without it the binary will not run. HARUSPEX is not a threat. Gatekeeper has been informed. It remains unconvinced.

This is a terminal application. Do not double-click it in Finder. It will open as a text file. This is not useful.

### Linux

```bash
chmod +x haruspex-linux
./haruspex-linux
```

### Windows

Download `haruspex-windows.exe` and run it from a terminal (Command Prompt or PowerShell). Double-clicking may work, but a terminal window is required for the interface to render. If Windows Defender objects, click "More info" → "Run anyway". HARUSPEX has noted this is not an ideal onboarding experience.

---

**Running from source** — requires Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/mogglemoss/haruspex
cd haruspex
uv sync
uv run haruspex
```

---

## Configuration

HARUSPEX requires no configuration for D-Scan and Local. It knows what it needs to know. Live log monitoring is opt-in, on the reasonable grounds that reading your files without permission would be rude.

Create `~/.config/haruspex/config.toml` to enable it:

```toml
[logs]
enabled = true
```

HARUSPEX will auto-detect your EVE log directory on macOS, Linux (Steam/Proton), and Linux (Steam Flatpak). On Windows, the directory must be specified manually, because Windows remains, as ever, a place where things must be specified manually:

```toml
[logs]
enabled = true
path = "C:/Users/YourName/Documents/EVE/logs/Chatlogs"
```

**Log monitoring is TOS-compliant.** CCP writes these files specifically for third-party tool consumption. HARUSPEX is a third party. CCP has not objected to this characterisation. This situation may continue indefinitely.

**Configurable wormhole affiliations** — HARUSPEX ships with a curated list of known wormhole corporations and alliances. You may extend this list at your own discretion and risk:

```toml
[logs]
enabled = true
wh_corps = ["my secret wh corp", "that other group"]
wh_alliances = ["the coalition we don't talk about"]
```

Entries are matched as case-insensitive substrings. HARUSPEX does not judge your associations. HARUSPEX has noted them.

---

## Keybindings

| Key | Action |
|-----|--------|
| `d` | D-Scan panel |
| `l` | Local intel panel |
| `m` | Monitoring panel |
| `Esc` | Return to overview |
| `c` | Copy intel summary to clipboard |
| `?` | Help overlay |
| `Ctrl+R` | Clear current panel |
| `q` | Quit |

From the overview, `c` copies a combined summary of all three panels simultaneously. HARUSPEX has prepared this text. Whether you paste it into fleet chat is between you and your fleet commander.

Clicking any overview card opens that panel. This works as expected. HARUSPEX is pleased by this.

---

## Technical Specifications

| Component | Detail |
|-----------|--------|
| D-Scan engine | Local · bundled SDE corpus · no network |
| Hull coverage | 529 types · 46 groups · drone classes |
| Signals of Interest | 40 flagged hulls · 10 tactical categories · threat-priority order |
| Fleet archetypes | 8 detected types · gate camp · WH gang · doctrine fleet · black ops · capital · and others |
| Field conditions | MTU · deployed bubble · cyno field · combat probes · core probes · wrecks · and others |
| Threat model | Empirical · ship count · logistics ratio · hull composition |
| Name resolution | ESI `/universe/ids/` · bulk |
| Kill data | zKillboard public API · rate-limited · 3 concurrent |
| Danger threshold | ≥50% danger ratio AND ≥10 kills |
| Log format | UTF-16LE · 1 s poll interval |
| Network required | D-Scan: no · Local + Monitoring: yes |
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

| Platform | Binaries | Log Auto-Detection |
|----------|----------|--------------------|
| macOS | Universal (arm64 + x86_64) | Yes |
| Linux (native) | Yes | Yes |
| Linux (Steam/Proton) | Yes | Yes |
| Linux (Steam Flatpak) | Yes | Yes |
| Windows | Yes | Set path in config |

---

## A Note on Intelligence

HARUSPEX produces assessments, not facts. A pilot with zero kills on zKillboard may be a peaceful hauler. They may also be a veteran with a private killboard and a deep personal commitment to your destruction. HARUSPEX cannot tell the difference. Neither can you, most of the time, which is at least a shared limitation.

A clean D-scan does not mean the system is empty. It means the system appears empty to your directional scanner. These are related but not identical conditions. HARUSPEX has opinions about this distinction and has incorporated them into its threat model, to the extent that a threat model can have opinions.

The system is most useful when combined with spatial awareness, good intel habits, and the kind of quiet suspicion that wormhole space instills in those who survive it long enough to develop opinions.

Fly accordingly.

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built with [Textual](https://textual.textualize.io). Uses the [EVE Online ESI API](https://esi.evetech.net). Not affiliated with or endorsed by CCP Games. EVE Online and all related marks are the intellectual property of CCP hf.*

---

— [Cormorant Fell](https://evewho.com/character/93594488), probably in a wormhole
