from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class RiskLevel(str, Enum):
    SAFE = "safe"
    REVIEW = "review"
    DANGER = "danger"


class CleanupMethod(str, Enum):
    COMMAND = "command"
    DIRECTORY = "directory"
    NONE = "none"


@dataclass
class CacheItem:
    id: str
    name: str
    ecosystem: str
    path: str
    size_bytes: int
    risk_level: RiskLevel
    description: str
    long_description: str
    cleanup_method: CleanupMethod
    cleanup_command: Optional[str] = None
    icon_name: str = "folder"
    exists: bool = True
    sub_items: list = field(default_factory=list)

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024 * 1024 * 1024)

    @property
    def size_label(self) -> str:
        if self.size_bytes >= 1024 ** 3:
            return f"{self.size_gb:.2f} GB"
        elif self.size_bytes >= 1024 ** 2:
            return f"{self.size_mb:.1f} MB"
        elif self.size_bytes >= 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        return f"{self.size_bytes} B"

    @property
    def risk_label(self) -> str:
        return {
            RiskLevel.SAFE: "Safe",
            RiskLevel.REVIEW: "Review",
            RiskLevel.DANGER: "Danger",
        }[self.risk_level]
