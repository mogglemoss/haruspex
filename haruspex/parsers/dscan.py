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
}

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
    threat: str = ""

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
    filtered.threat = _assess_threat(filtered)
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
    return result


def _classify(result: DscanResult, ships: dict, ship_type: str) -> None:
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
    if "wreck" in ship_type.lower():
        result.wrecks += 1
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
