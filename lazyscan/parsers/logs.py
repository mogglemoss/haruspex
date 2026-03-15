"""EVE chatlog file tailer — UTF-16LE, async."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

# [ 2024.01.15 20:34:12 ] CharacterName > message
_LOG_RE = re.compile(
    r"\[ (\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}) \] (.+?) > (.*)"
)

PILOT_JOINED = "has joined the channel"
PILOT_LEFT = "has left the channel"


@dataclass
class LogEvent:
    timestamp: str
    sender: str
    message: str

    @property
    def is_system(self) -> bool:
        return self.sender == "EVE System"

    @property
    def pilot_joined(self) -> str | None:
        """Return pilot name if this is a join event, else None."""
        if self.is_system and PILOT_JOINED in self.message:
            # "CharacterName has joined the channel"
            name = self.message.replace(PILOT_JOINED, "").strip()
            return name or None
        return None

    @property
    def pilot_left(self) -> str | None:
        if self.is_system and PILOT_LEFT in self.message:
            name = self.message.replace(PILOT_LEFT, "").strip()
            return name or None
        return None

    @property
    def system_changed(self) -> str | None:
        """Return system name if this is a 'Channel changed to Local' event."""
        if self.is_system and "Channel changed to Local :" in self.message:
            return self.message.split(":", 1)[1].strip() or None
        return None


def _latest_local_log(chatlog_dir: Path) -> Path | None:
    """Return the most recently modified Local_*.txt in chatlog_dir."""
    logs = sorted(
        chatlog_dir.glob("Local_*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return logs[0] if logs else None


def _parse_line(line: str) -> LogEvent | None:
    m = _LOG_RE.match(line.strip().lstrip('\ufeff'))
    if not m:
        return None
    return LogEvent(timestamp=m.group(1), sender=m.group(2), message=m.group(3))


async def tail(
    chatlog_dir: Path,
    on_event: callable,
    poll_interval: float = 1.0,
) -> None:
    """
    Tail the most recent Local_*.txt log in chatlog_dir.

    Calls on_event(LogEvent) for each new line. Switches to a newer log
    file if one appears (e.g. when jumping to a new system resets the log).

    Runs until cancelled.
    """
    current_path: Path | None = None
    file_handle = None
    position: int = 0

    try:
        while True:
            latest = _latest_local_log(chatlog_dir)

            # Switch file if a newer log appeared
            if latest != current_path:
                if file_handle:
                    file_handle.close()
                current_path = latest
                if current_path is None:
                    await asyncio.sleep(poll_interval)
                    continue
                file_handle = open(current_path, encoding="utf-16-le", errors="replace")
                # Replay existing content for system-change events only, then tail from end
                existing = file_handle.read()
                for line in existing.splitlines():
                    event = _parse_line(line)
                    if event and event.system_changed:
                        await on_event(event)
                position = file_handle.tell()

            if file_handle is None:
                await asyncio.sleep(poll_interval)
                continue

            # Read any new content
            file_handle.seek(position)
            new_data = file_handle.read()
            if new_data:
                position = file_handle.tell()
                for line in new_data.splitlines():
                    event = _parse_line(line)
                    if event:
                        await on_event(event)

            await asyncio.sleep(poll_interval)

    except asyncio.CancelledError:
        pass
    finally:
        if file_handle:
            file_handle.close()
