#!/usr/bin/env python3
"""Build lazyscan/data/ships.json from ESI ship type data."""
import asyncio
import json
import httpx

ESI = "https://esi.evetech.net/latest"

# ESI group_id -> lazyscan class, group_name
GROUP_MAP = {
    25:   ("combat",  "Frigate"),
    26:   ("combat",  "Cruiser"),
    27:   ("combat",  "Battleship"),
    28:   ("hauler",  "Hauler"),
    29:   ("other",   "Capsule"),
    30:   ("combat",  "Titan"),
    31:   ("other",   "Shuttle"),
    237:  ("other",   "Corvette"),
    324:  ("combat",  "Assault Frigate"),
    358:  ("combat",  "Heavy Assault Cruiser"),
    380:  ("hauler",  "Deep Space Transport"),
    381:  ("combat",  "Elite Battleship"),
    419:  ("combat",  "Combat Battlecruiser"),
    420:  ("combat",  "Destroyer"),
    513:  ("hauler",  "Freighter"),
    540:  ("combat",  "Command Ship"),
    541:  ("combat",  "Interdictor"),
    543:  ("other",   "Exhumer"),
    547:  ("combat",  "Carrier"),
    659:  ("combat",  "Supercarrier"),
    830:  ("recon",   "Covert Ops"),
    831:  ("combat",  "Interceptor"),
    832:  ("logi",    "Logistics"),
    833:  ("recon",   "Force Recon Ship"),
    834:  ("combat",  "Stealth Bomber"),
    883:  ("hauler",  "Capital Industrial Ship"),
    893:  ("combat",  "Electronic Attack Ship"),
    894:  ("combat",  "Heavy Interdictor"),
    898:  ("combat",  "Black Ops"),
    900:  ("combat",  "Marauder"),
    902:  ("hauler",  "Jump Freighter"),
    906:  ("recon",   "Combat Recon Ship"),
    941:  ("hauler",  "Industrial Command Ship"),
    963:  ("combat",  "Strategic Cruiser"),
    1022: ("other",   "Prototype Exploration Ship"),
    1201: ("combat",  "Attack Battlecruiser"),
    1202: ("hauler",  "Blockade Runner"),
    1283: ("other",   "Expedition Frigate"),
    1305: ("combat",  "Tactical Destroyer"),
    1527: ("logi",    "Logistics Frigate"),
    1534: ("combat",  "Command Destroyer"),
    1538: ("logi",    "Force Auxiliary"),
    1972: ("combat",  "Flag Cruiser"),
    2001: ("other",   "Citizen Ships"),
    4594: ("combat",  "Dreadnought"),
    4902: ("combat",  "Expedition Command Ship"),
}

# ESI category 18 — Drones
DRONE_GROUP_MAP = {
    100:  ("drone", "Combat Drone"),
    101:  ("drone", "Mining Drone"),
    299:  ("drone", "Repair Drone"),
    544:  ("drone", "Combat Drone"),
    545:  ("drone", "Combat Drone"),
    639:  ("drone", "Combat Drone"),
    640:  ("drone", "Logistics Drone"),
    641:  ("drone", "Combat Drone"),
    1159: ("drone", "Salvage Drone"),
    # Fighters (launched from carriers/supercarriers)
    549:  ("fighter", "Fighter"),
    1023: ("fighter", "Fighter Bomber"),
}

SEMAPHORE = asyncio.Semaphore(20)


async def fetch_json(client: httpx.AsyncClient, url: str) -> dict | list:
    async with SEMAPHORE:
        r = await client.get(url, timeout=30)
        r.raise_for_status()
        return r.json()


async def fetch_group_types(client: httpx.AsyncClient, group_id: int) -> list[int]:
    data = await fetch_json(client, f"{ESI}/universe/groups/{group_id}/")
    return data.get("types", [])


async def fetch_type_name(client: httpx.AsyncClient, type_id: int) -> str | None:
    data = await fetch_json(client, f"{ESI}/universe/types/{type_id}/")
    if data.get("published", False):
        return data.get("name")
    return None


async def main():
    ships = {}
    all_groups = {**GROUP_MAP, **DRONE_GROUP_MAP}
    print(f"Fetching types for {len(all_groups)} groups (ships + drones)...")

    async with httpx.AsyncClient() as client:
        # Fetch all type IDs for each group
        group_tasks = {
            group_id: asyncio.create_task(fetch_group_types(client, group_id))
            for group_id in all_groups
        }
        group_types: dict[int, list[int]] = {}
        for group_id, task in group_tasks.items():
            try:
                type_ids = await task
                group_types[group_id] = type_ids
                cls, grp_name = all_groups[group_id]
                print(f"  {grp_name}: {len(type_ids)} types")
            except Exception as e:
                print(f"  ERROR group {group_id}: {e}")
                group_types[group_id] = []

        # Fetch all type names
        all_tasks: list[tuple[int, int, asyncio.Task]] = []
        for group_id, type_ids in group_types.items():
            for type_id in type_ids:
                task = asyncio.create_task(fetch_type_name(client, type_id))
                all_tasks.append((group_id, type_id, task))

        print(f"\nFetching {len(all_tasks)} type names...")
        for i, (group_id, type_id, task) in enumerate(all_tasks):
            try:
                name = await task
                if name:
                    cls, grp_name = all_groups[group_id]
                    ships[name] = {"class": cls, "group": grp_name}
            except Exception as e:
                print(f"  ERROR type {type_id}: {e}")
            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(all_tasks)} done...")

    output_path = "lazyscan/data/ships.json"
    with open(output_path, "w") as f:
        json.dump(ships, f, sort_keys=True, indent=2)

    print(f"\nWrote {len(ships)} ships to {output_path}")
    cls_counts = {}
    for v in ships.values():
        cls_counts[v["class"]] = cls_counts.get(v["class"], 0) + 1
    for cls, count in sorted(cls_counts.items()):
        print(f"  {cls}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
