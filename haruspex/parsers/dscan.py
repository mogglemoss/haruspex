"""D-scan clipboard text parser."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Notable hulls to flag — {name: display label}
NOTABLE_HULLS: dict[str, str] = {
    # Combat recons
    "Pilgrim": "Combat Recon",
    "Curse": "Combat Recon",
    "Huginn": "Combat Recon",
    "Rapier": "Combat Recon",
    "Lachesis": "Combat Recon",
    "Arazu": "Combat Recon",
    # Black ops
    "Redeemer": "Black Ops",
    "Sin": "Black Ops",
    "Widow": "Black Ops",
    "Panther": "Black Ops",
    # Heavy interdictors
    "Devoter": "Heavy Interdictor",
    "Onyx": "Heavy Interdictor",
    "Broadsword": "Heavy Interdictor",
    "Phobos": "Heavy Interdictor",
    # Interdictors
    "Sabre": "Interdictor",
    "Flycatcher": "Interdictor",
    "Heretic": "Interdictor",
    "Eris": "Interdictor",
    # Strategic cruisers
    "Loki": "Strategic Cruiser",
    "Tengu": "Strategic Cruiser",
    "Proteus": "Strategic Cruiser",
    "Legion": "Strategic Cruiser",
    # Covert hunters
    "Stratios": "Covert Hunter",
    "Astero": "Covert Hunter",
    "Helios": "Covert Ops",
    "Buzzard": "Covert Ops",
    "Cheetah": "Covert Ops",
    "Anathema": "Covert Ops",
    "Imicus": "Exploration Frigate",
    # Combat recons — Caldari pair completes the set
    "Falcon": "Combat Recon",
    "Rook": "Combat Recon",
    # Command ships — presence implies an organised boosting doctrine
    "Eos": "Command Ship",
    "Damnation": "Command Ship",
    "Claymore": "Command Ship",
    "Vulture": "Command Ship",
    "Absolution": "Command Ship",
    "Astarte": "Command Ship",
    "Nighthawk": "Command Ship",
    "Sleipnir": "Command Ship",
    # Logistics battleship — rare, significant; can also field fighters
    "Nestor": "Logistics Battleship",
}

# Combat Recon Ships have a passive role bonus that reduces sensor strength to zero,
# making them invisible to directional scanners. Seeing one on scan is unusual.
_DSCAN_IMMUNE: frozenset[str] = frozenset({
    "Falcon", "Rook", "Huginn", "Rapier", "Lachesis", "Arazu",
})

# Player-built structures
_STRUCTURE_KW = (
    "Keepstar", "Fortizar", "Astrahus",
    "Raitaru", "Azbel", "Tatara", "Athanor",
    "Engineering Complex", "Refinery", "Citadel",
    "Control Tower",
    "Customs Office",
    "Assembly Array", "Storage Array", "Refining Array",
    "Reactor", "Silo", "Hangar", "Laboratory", "Factory",
    "Battery", "Turret", "Launcher",
    "Shield Hardener", "Sensor Array",
)

# Deployable objects (mobile structures)
_DEPLOYABLE_KW = (
    "Mobile Depot",
    "Mobile Tractor Unit",
    "Mobile Cyno Inhibitor",
    "Mobile Warp Disruptor",
    "Mobile Warp Scrambler",
    "Mobile Micro Jump Unit",
    "Mobile Scan Inhibitor",
    "Mobile Siphon Unit",
    "Mobile Small Warp Disruptor",
    "Mobile Medium Warp Disruptor",
    "Mobile Large Warp Disruptor",
    "Mobile Artillery",
    "Mobile Hybrid",
    "Mobile Laser",
    "Mobile Projectile",
    "Mobile Missile",
    "Encounter Surveillance System",
    "Upwell Cynosural Beacon",
    "Cynosural Field Generator",
)

# Celestial navigation objects (noise — don't count for threat)
_CELESTIAL_KW = (
    "Stargate", "Station", "Outpost",
    "Planet", "Moon", "Sun", "Star",
    "Asteroid Belt", "Ice Belt",
    "Jump Gate",
)

# NPC factions — type names contain these
_NPC_KW = (
    "Sleeper", "Drifter", "Circadian",
    "Sansha", "Blood", "Guristas", "Serpentis",
    "Angel", "Cartel", "Mordu", "Rogue Drone",
    "Pirate", "Mercenary", "Triglavian", "Edencom",
    "CONCORD", "Navy", "Faction",
)


def _load_ships() -> dict[str, dict]:
    data_path = Path(__file__).parent.parent / "data" / "ships.json"
    with open(data_path) as f:
        return json.load(f)


_SHIPS: dict[str, dict] | None = None


def _ships() -> dict[str, dict]:
    global _SHIPS
    if _SHIPS is None:
        _SHIPS = _load_ships()
    return _SHIPS


def _kw_match(text: str, keywords: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(kw.lower() in low for kw in keywords)


@dataclass
class DscanEntry:
    distance: str
    name: str
    ship_type: str

    @property
    def distance_km(self) -> float | None:
        raw = self.distance.replace(",", "").strip()
        if raw.endswith(" km"):
            try:
                return float(raw[:-3])
            except ValueError:
                pass
        return None


@dataclass
class DscanResult:
    entries: list[DscanEntry] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)  # ship classes
    notable: dict[str, int] = field(default_factory=dict)
    # non-ship categories
    drones: int = 0
    fighters: int = 0
    structures: int = 0
    deployables: int = 0
    celestials: int = 0
    wrecks: int = 0
    npcs: int = 0
    cosmic: int = 0   # anomalies, signatures, wormholes
    unknown: int = 0
    core_probes: int = 0
    combat_probes: int = 0
    mtu: int = 0                    # Mobile Tractor Unit — implies active site
    warp_disruption_probes: int = 0 # Deployed dictor bubble — something being caught
    cyno_fields: int = 0            # Cynosural field active — capital bridge
    threat: str = ""
    archetype: str = ""
    # Ordered list of (color, label, text) assessment lines for display
    assessments: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def total_ships(self) -> int:
        return sum(self.counts.values())

    @property
    def total_objects(self) -> int:
        return len(self.entries)

    def pct(self, cls: str) -> int:
        total = self.total_ships
        if total == 0:
            return 0
        return round(self.counts.get(cls, 0) / total * 100)


def filter_by_range(result: DscanResult, max_km: float) -> DscanResult:
    """Return a new DscanResult containing only entries within max_km."""
    ships = _ships()
    filtered = DscanResult()
    for entry in result.entries:
        km = entry.distance_km
        if km is None or km > max_km:
            continue
        filtered.entries.append(entry)
        _classify(filtered, ships, entry.ship_type)
        if entry.ship_type in NOTABLE_HULLS:
            filtered.notable[entry.ship_type] = filtered.notable.get(entry.ship_type, 0) + 1
    # Probes are rarely on-grid but are whole-system intel — carry from full scan
    filtered.core_probes = result.core_probes
    filtered.combat_probes = result.combat_probes
    filtered.threat = _assess_threat(filtered)
    filtered.archetype = _detect_archetype(filtered)
    filtered.assessments = _build_assessments(filtered)
    return filtered


def parse(text: str) -> DscanResult:
    ships = _ships()
    result = DscanResult()

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            parts = re.split(r"  +", line, maxsplit=2)
        if len(parts) < 3:
            continue

        distance, name, ship_type = parts[0].strip(), parts[1].strip(), parts[2].strip()
        entry = DscanEntry(distance=distance, name=name, ship_type=ship_type)
        result.entries.append(entry)

        _classify(result, ships, ship_type)

        if ship_type in NOTABLE_HULLS:
            result.notable[ship_type] = result.notable.get(ship_type, 0) + 1

    result.threat = _assess_threat(result)
    result.archetype = _detect_archetype(result)
    result.assessments = _build_assessments(result)
    return result


def _classify(result: DscanResult, ships: dict, ship_type: str) -> None:
    low = ship_type.lower()

    # 0. Probes — intercept before ships.json
    if "combat scanner probe" in low:
        result.combat_probes += 1
        return
    if "core scanner probe" in low:
        result.core_probes += 1
        return

    # 1. Known ship/drone from ships.json
    if ship_type in ships:
        cls = ships[ship_type]["class"]
        if cls == "drone":
            result.drones += 1
        elif cls == "fighter":
            result.fighters += 1
        else:
            result.counts[cls] = result.counts.get(cls, 0) + 1
        return

    # 2. Wreck
    if "wreck" in low:
        result.wrecks += 1
        return

    # 3a. Cynosural field — intercept before deployables (_DEPLOYABLE_KW contains it)
    if "cynosural field" in low:
        result.cyno_fields += 1
        return

    # 3b. Mobile Tractor Unit — intercept before deployables for distinct tracking
    if ship_type == "Mobile Tractor Unit":
        result.mtu += 1
        return

    # 3c. Warp Disruption Probe (launched by interdictors — not the anchored structure)
    if "warp disruption probe" in low and "mobile" not in low:
        result.warp_disruption_probes += 1
        return

    # 3. Cosmic anomaly / signature / wormhole
    if ship_type in ("Cosmic Anomaly", "Cosmic Signature") or \
       "wormhole" in ship_type.lower() or \
       "beacon" in ship_type.lower() or \
       "acceleration gate" in ship_type.lower():
        result.cosmic += 1
        return

    # 4. Celestials
    if _kw_match(ship_type, _CELESTIAL_KW):
        result.celestials += 1
        return

    # 5. Deployables
    if _kw_match(ship_type, _DEPLOYABLE_KW) or \
       ship_type.startswith("Mobile "):
        result.deployables += 1
        return

    # 6. Player structures
    if _kw_match(ship_type, _STRUCTURE_KW):
        result.structures += 1
        return

    # 7. NPCs
    if _kw_match(ship_type, _NPC_KW):
        result.npcs += 1
        return

    result.unknown += 1


def _hull_cats(notable: dict[str, int]) -> dict[str, int]:
    """Count notable hulls by tactical category."""
    cats: dict[str, int] = {}
    for hull, count in notable.items():
        cat = NOTABLE_HULLS.get(hull, "")
        if cat:
            cats[cat] = cats.get(cat, 0) + count
    return cats


def _detect_archetype(r: DscanResult) -> str:
    total = r.total_ships
    if total == 0:
        return ""

    cats = _hull_cats(r.notable)
    combat  = r.counts.get("combat", 0)
    recon   = r.counts.get("recon", 0)
    logi    = r.counts.get("logi", 0)
    hauler  = r.counts.get("hauler", 0)

    dictor  = cats.get("Interdictor", 0)
    hic     = cats.get("Heavy Interdictor", 0)
    blops   = cats.get("Black Ops", 0)
    t3      = cats.get("Strategic Cruiser", 0)
    crecon  = cats.get("Combat Recon", 0)
    covert  = cats.get("Covert Hunter", 0) + cats.get("Covert Ops", 0)

    # Capital escalation — fighters mean a carrier is somewhere
    if r.fighters > 0:
        return "Capital escalation"

    # Black ops — very specific hull, high confidence
    if blops > 0:
        return "Black ops drop"

    # Gate / pipe camp — tackle + guns
    if (dictor + hic) >= 1 and combat >= 1:
        return "Gate camp"

    # WH hunter gang — T3s and/or covert hunters, tight group
    if (t3 + crecon + covert) >= 2 and total <= 12 and logi == 0:
        return "WH hunter gang"

    # Solo cloaked hunter
    if total <= 2 and (t3 + crecon + covert) >= 1:
        return "Cloaked hunter"

    # Organised brawl — logi on field means they planned this
    if logi >= 2 and combat >= 4:
        if recon >= 1:
            return "Doctrine fleet · ewar wing"
        return "Doctrine fleet"

    # Nano roam — recons + no logi, small and fast
    if recon >= 1 and combat >= 2 and logi == 0 and total <= 15:
        return "Nano roam"

    # PvE — haulers or no tackle/recon present
    if hauler >= 1 and (dictor + hic + crecon + t3) == 0:
        return "PvE activity"

    return ""


def _assess_threat(r: DscanResult) -> str:
    total = r.total_ships
    logi = r.counts.get("logi", 0)

    if total == 0 and r.structures > 0:
        return "Infrastructure detected. No witnesses."
    if total == 0:
        return "Scan nominal. Suspiciously quiet."
    if total == 1:
        return "Solo operator. Could be bait."
    if total <= 5:
        return "Small engagement party. Festive."
    if total <= 15:
        if logi > 0:
            return "Medium gang. Sustained engagement capability noted."
        return "Medium gang. Someone has a plan."
    if total <= 40:
        if logi >= 3:
            return "Large gang with logistics. They intend to stay."
        return "Large gang. Recommend introspection."
    if logi >= 5:
        return "Fleet-scale remediation team. HARUSPEX wishes you well."
    return "Fleet detected. Adjust expectations accordingly."


def _build_assessments(r: DscanResult) -> list[tuple[str, str, str]]:
    """Return ordered (severity, label, text) assessment lines.

    Severity values: 'dim' | 'low' | 'medium' | 'high' | 'critical'
    Resolved to display colors in the panel.
    """
    items: list[tuple[str, str, str]] = []

    # Fleet threat
    _threat_severity = {
        "Infrastructure detected. No witnesses.":                   "dim",
        "Scan nominal. Suspiciously quiet.":                        "dim",
        "Solo operator. Could be bait.":                            "low",
        "Small engagement party. Festive.":                         "low",
        "Medium gang. Someone has a plan.":                         "medium",
        "Medium gang. Sustained engagement capability noted.":      "medium",
        "Large gang. Recommend introspection.":                     "medium",
        "Large gang with logistics. They intend to stay.":          "high",
        "Fleet-scale remediation team. HARUSPEX wishes you well.":  "high",
        "Fleet detected. Adjust expectations accordingly.":         "high",
    }
    items.append((_threat_severity.get(r.threat, "low"), "threat", r.threat))

    # Fleet archetype
    if r.archetype:
        items.append(("medium", "fleet type", r.archetype))

    # Logistics ratio — meaningful when logi is significant relative to combat
    combat = r.counts.get("combat", 0)
    logi = r.counts.get("logi", 0)
    if logi >= 1 and combat >= 2:
        ratio = round(logi / (combat + logi) * 100)
        if ratio >= 30:
            items.append(("high", "logistics", f"{ratio}% logi coverage — heavily supported. Breaking this requires commitment."))
        elif ratio >= 20:
            items.append(("medium", "logistics", f"{ratio}% logi coverage — sustained engagement capability."))
        elif ratio >= 15:
            items.append(("low", "logistics", f"{ratio}% logi coverage — light support presence."))

    # Probe intel — independent of ship count, always shown when present
    if r.combat_probes:
        n = f" ×{r.combat_probes}" if r.combat_probes > 1 else ""
        items.append(("high", "combat probes", f"Combat probes on scan{n}. A hunter is active. You may be the target."))
    if r.core_probes:
        n = f" ×{r.core_probes}" if r.core_probes > 1 else ""
        items.append(("low", "core probes", f"Core probes on scan{n}. System is being scanned."))

    # Warp disruption probe — active bubble, something is being caught
    if r.warp_disruption_probes:
        n = f" ×{r.warp_disruption_probes}" if r.warp_disruption_probes > 1 else ""
        items.append(("high", "bubble", f"Warp disruption probe on scan{n}. Something is being caught."))

    # Cynosural field — capital bridge active, show last for emphasis
    if r.cyno_fields:
        n = f" ×{r.cyno_fields}" if r.cyno_fields > 1 else ""
        items.append(("critical", "cyno field", f"Cynosural field active{n}. Whatever was invited has arrived."))

    return items
