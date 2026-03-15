"""zKillboard API enrichment — character kill stats."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

ZKILL = "https://zkillboard.com/api"
HEADERS = {
    "Accept-Encoding": "gzip",
    "User-Agent": "lazyscan/0.1 github.com/mogglemoss/lazyscan",
}

# Known wormhole corps/alliances to flag (name fragments, case-insensitive)
WH_CORPS = {
    "wingspan delivery services",
    "hard knocks citizens",
    "lazerhawks",
    "no vacancies",
    "hole control",
    "the dark space initiative",
    "scary wormhole people",
    "future corps",
    "night crew",
    "inner hell",
}

WH_ALLIANCES = {
    "wingspan delivery network",
    "hard knocks",
    "lazerhawks",
    "no vacancies.",
    "the initiative.",
}

WINGSPAN_CORP = "wingspan delivery services"


@dataclass
class ZkillStats:
    character_id: int
    kills: int = 0
    losses: int = 0
    danger_ratio: int = 0   # 0-100, higher = more dangerous
    gang_ratio: int = 0     # 0-100, higher = more solo
    last_seen: str = ""
    error: str = ""

    @property
    def dangerous(self) -> bool:
        return self.danger_ratio >= 50 and self.kills >= 10


async def _fetch_stats(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, character_id: int
) -> ZkillStats:
    async with sem:
        r = await client.get(
            f"{ZKILL}/stats/characterID/{character_id}/",
            timeout=20,
            headers=HEADERS,
        )
        r.raise_for_status()
        data = r.json()
        await asyncio.sleep(0.1)  # be polite between requests

    # zKill returns {"error": ...} for characters with no kill history
    if "error" in data:
        return ZkillStats(character_id=character_id)

    stats = ZkillStats(character_id=character_id)
    stats.kills = data.get("shipsDestroyed", 0)
    stats.losses = data.get("shipsLost", 0)
    stats.danger_ratio = data.get("dangerRatio", 0)
    stats.gang_ratio = data.get("gangRatio", 0)
    return stats


async def fetch_all(character_ids: list[int]) -> dict[int, ZkillStats]:
    """Fetch zKillboard stats for a list of character IDs concurrently."""
    sem = asyncio.Semaphore(3)  # conservative — zKillboard rate-limits aggressively
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[_fetch_stats(client, sem, cid) for cid in character_ids],
            return_exceptions=True,
        )
    return {
        cid: (r if not isinstance(r, Exception) else ZkillStats(character_id=cid, error=str(r)))
        for cid, r in zip(character_ids, results)
    }


def is_wh_corp(corp_name: str) -> bool:
    low = corp_name.lower()
    return any(wh in low for wh in WH_CORPS)


def is_wh_alliance(alliance_name: str) -> bool:
    low = alliance_name.lower()
    return any(wh in low for wh in WH_ALLIANCES)


def is_wingspan(corp_name: str, alliance_name: str) -> bool:
    return (
        WINGSPAN_CORP in corp_name.lower()
        or "wingspan" in alliance_name.lower()
    )
