from dataclasses import dataclass, field
from typing import List
from .cache_item import CacheItem


@dataclass
class ScanResult:
    items: List[CacheItem] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    scanner_name: str = ""

    @property
    def total_bytes(self) -> int:
        return sum(i.size_bytes for i in self.items)

    @property
    def item_count(self) -> int:
        return len(self.items)
