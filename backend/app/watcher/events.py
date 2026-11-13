"""Event models for filesystem change monitoring."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import time
from typing import Optional


class FileChangeType(str, Enum):
    """Types of filesystem change events monitored by OmniSearch."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass(frozen=True)
class FileChangeEvent:
    """Represents a discrete or coalesced filesystem change event."""

    change_type: FileChangeType
    path: Path
    dest_path: Optional[Path] = None
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            object.__setattr__(self, "timestamp", time.time())

