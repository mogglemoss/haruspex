"""Tests for D-scan parser."""
from pathlib import Path

import pytest

from haruspex.parsers.dscan import parse

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_small_gang():
    result = parse(load("small_gang.txt"))
    assert result.total_ships == 5
    assert result.counts["combat"] == 2   # Loki, Sabre (combat class)
    assert result.counts["recon"] == 2    # Huginn, Lachesis
    assert result.counts["logi"] == 1     # Scimitar
    assert "Loki" in result.notable
    assert "Sabre" in result.notable
    assert "Huginn" in result.notable
    assert "Lachesis" in result.notable


def test_structures_only():
    result = parse(load("structures_only.txt"))
    assert result.total_ships == 0
    assert result.structures == 4
    assert result.threat == "Structures only"


def test_solo_hunter():
    result = parse(load("solo_hunter.txt"))
    assert result.total_ships == 1
    assert result.threat == "Solo"
    assert "Stratios" in result.notable


def test_combat_fleet():
    result = parse(load("combat_fleet.txt"))
    assert result.total_ships >= 15
    assert result.counts.get("logi", 0) >= 2
    assert "Fleet" in result.threat or "gang" in result.threat
    assert "Huginn" in result.notable
    assert "Sabre" in result.notable
    assert "Onyx" in result.notable


def test_empty_input():
    result = parse("")
    assert result.total_ships == 0
    assert result.threat == "No ships"


def test_pct():
    result = parse(load("small_gang.txt"))
    assert result.pct("logi") == 20   # 1/5
    assert result.pct("recon") == 40  # 2/5


def test_non_ship_categories():
    text = "\n".join([
        "1,000 km\tHobgoblin II\tHobgoblin II",
        "2,000 km\tBouncer I\tBouncer I",
        "3,000 km\tRifter Wreck\tRifter Wreck",
        "4,000 km\tAstero Wreck\tAstero Wreck",
        "- AU\tSome Anomaly\tCosmic Anomaly",
        "- AU\tA Wormhole\tUnstable Wormhole",
        "- AU\tMy Depot\tMobile Depot",
        "- AU\tGate\tStargate (Jita)",
        "- AU\tHome\tAstrahus",
    ])
    result = parse(text)
    assert result.drones == 2
    assert result.wrecks == 2
    assert result.cosmic == 2
    assert result.deployables == 1
    assert result.celestials == 1
    assert result.structures == 1
    assert result.total_ships == 0
