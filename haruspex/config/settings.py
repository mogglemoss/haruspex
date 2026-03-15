"""haruspex configuration — stored at ~/.config/haruspex/config.toml."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

CONFIG_DIR = Path.home() / ".config" / "haruspex"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Candidate log paths per platform, in priority order
_LOG_CANDIDATES: list[Path] = [
    # macOS
    Path.home() / "Documents" / "EVE" / "logs" / "Chatlogs",
    # Windows (under WSL or native)
    Path.home() / "Documents" / "EVE" / "logs" / "Chatlogs",
    # Linux — Steam/Proton
    Path.home() / ".local" / "share" / "Steam" / "steamapps" / "compatdata" / "8500"
    / "pfx" / "drive_c" / "users" / "steamuser" / "My Documents" / "EVE" / "logs" / "Chatlogs",
    # Linux — Steam flatpak
    Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam"
    / "steamapps" / "compatdata" / "8500" / "pfx" / "drive_c" / "users" / "steamuser"
    / "My Documents" / "EVE" / "logs" / "Chatlogs",
]


def detect_log_path() -> Path | None:
    """Return the first existing EVE chatlog directory, or None."""
    for p in _LOG_CANDIDATES:
        if p.exists():
            return p
    return None


@dataclass
class LogsConfig:
    enabled: bool = False
    path: str = ""
    intel_channels: list[str] = field(default_factory=list)
    wh_corps: list[str] = field(default_factory=list)
    wh_alliances: list[str] = field(default_factory=list)

    @property
    def log_path(self) -> Path | None:
        if self.path:
            p = Path(self.path).expanduser()
            return p if p.exists() else None
        return detect_log_path()


@dataclass
class Config:
    logs: LogsConfig = field(default_factory=LogsConfig)

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "logs": {
                "enabled": self.logs.enabled,
                "path": self.logs.path,
                "intel_channels": self.logs.intel_channels,
                "wh_corps": self.logs.wh_corps,
                "wh_alliances": self.logs.wh_alliances,
            }
        }
        CONFIG_FILE.write_bytes(tomli_w.dumps(data).encode())

    @classmethod
    def load(cls) -> "Config":
        if not CONFIG_FILE.exists():
            return cls()
        try:
            data = tomllib.loads(CONFIG_FILE.read_text())
            logs_data = data.get("logs", {})
            return cls(
                logs=LogsConfig(
                    enabled=logs_data.get("enabled", False),
                    path=logs_data.get("path", ""),
                    intel_channels=logs_data.get("intel_channels", []),
                    wh_corps=logs_data.get("wh_corps", []),
                    wh_alliances=logs_data.get("wh_alliances", []),
                )
            )
        except Exception:
            return cls()
