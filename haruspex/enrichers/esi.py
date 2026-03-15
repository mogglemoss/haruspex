"""ESI API enrichment — character/corp/alliance resolution."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

ESI = "https://esi.evetech.net/latest"


def _sem(n: int) -> asyncio.Semaphore:
    """Create a semaphore bound to the currently running loop."""
    return asyncio.Semaphore(n)


@dataclass
class CharacterInfo:
    name: str
    character_id: int | None = None
    corp_id: int | None = None
    corp_name: str = ""
    corp_ticker: str = ""
    alliance_id: int | None = None
    alliance_name: str = ""
    alliance_ticker: str = ""
    error: str = ""


async def enrich_characters(names: list[str]) -> list[CharacterInfo]:
    """Resolve names and fetch corp/alliance info for each character."""
    infos = {name: CharacterInfo(name=name) for name in names}
    sem = _sem(10)

    async def _get(client: httpx.AsyncClient, url: str) -> dict:
        async with sem:
            r = await client.get(url, timeout=15)
            r.raise_for_status()
            return r.json()

    async with httpx.AsyncClient() as client:
        # Step 1: bulk name → ID
        name_to_id = await _resolve_names(client, sem, names)
        for name, char_id in name_to_id.items():
            infos[name].character_id = char_id

        if not name_to_id:
            return list(infos.values())

        # Step 2: character details (corp_id, alliance_id)
        char_results = await asyncio.gather(
            *[_get(client, f"{ESI}/characters/{cid}/") for cid in name_to_id.values()],
            return_exceptions=True,
        )
        corp_ids: dict[str, int] = {}
        alliance_ids: dict[str, int] = {}
        for name, result in zip(name_to_id.keys(), char_results):
            if isinstance(result, Exception):
                infos[name].error = str(result)
                continue
            corp_id = result.get("corporation_id")
            alliance_id = result.get("alliance_id")
            if corp_id:
                infos[name].corp_id = corp_id
                corp_ids[name] = corp_id
            if alliance_id:
                infos[name].alliance_id = alliance_id
                alliance_ids[name] = alliance_id

        # Step 3: unique corp details
        unique_corps = list(set(corp_ids.values()))
        corp_results = await asyncio.gather(
            *[_get(client, f"{ESI}/corporations/{cid}/") for cid in unique_corps],
            return_exceptions=True,
        )
        corp_data = {
            cid: (r if not isinstance(r, Exception) else {})
            for cid, r in zip(unique_corps, corp_results)
        }

        # Step 4: unique alliance details
        unique_alliances = list(set(alliance_ids.values()))
        alliance_results = await asyncio.gather(
            *[_get(client, f"{ESI}/alliances/{aid}/") for aid in unique_alliances],
            return_exceptions=True,
        )
        alliance_data = {
            aid: (r if not isinstance(r, Exception) else {})
            for aid, r in zip(unique_alliances, alliance_results)
        }

        # Step 5: populate infos
        for name, info in infos.items():
            if info.corp_id and info.corp_id in corp_data:
                cd = corp_data[info.corp_id]
                info.corp_name = cd.get("name", "")
                info.corp_ticker = cd.get("ticker", "")
            if info.alliance_id and info.alliance_id in alliance_data:
                ad = alliance_data[info.alliance_id]
                info.alliance_name = ad.get("name", "")
                info.alliance_ticker = ad.get("ticker", "")

    return list(infos.values())


def _sanitise_names(names: list[str]) -> list[str]:
    """Deduplicate and filter names to valid ESI inputs."""
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        name = name.strip()
        # ESI rejects names > 100 chars or containing only whitespace
        if not name or len(name) > 100 or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


async def _resolve_names(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, names: list[str]
) -> dict[str, int]:
    results: dict[str, int] = {}
    clean = _sanitise_names(names)
    if not clean:
        return results
    for chunk in _chunks(clean, 500):
        async with sem:
            r = await client.post(
                f"{ESI}/universe/ids/",
                json=chunk,
                timeout=20,
            )
            if r.status_code == 400:
                # ESI returns 400 when none of the names resolve — not fatal
                continue
            r.raise_for_status()
            data = r.json()
            for entry in data.get("characters", []):
                results[entry["name"]] = entry["id"]
    return results


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]
