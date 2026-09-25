"""Data source seam. The UI depends on this Protocol, never on a concrete client, so
tests and screenshots use FakeSource and production swaps in a real one.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Item:
    key: str  # stable identity: becomes the DataTable row key
    name: str
    value: float
    change_pct: float
    status: str  # "ok" | "warn" | "down"


class Source(Protocol):
    async def fetch(self) -> list[Item]: ...

    def history(self, key: str) -> list[float]: ...


class FakeSource:
    """Deterministic random walk: stable for tests and screenshots."""

    def __init__(self, seed: int = 7, n: int = 8) -> None:
        self._rng = random.Random(seed)
        self._keys = [f"svc-{i:02d}" for i in range(n)]
        self._vals = {k: 100.0 + i * 10 for i, k in enumerate(self._keys)}
        self._hist = {k: [v] for k, v in self._vals.items()}

        for _ in range(30):  # warm history so charts look real from the first frame
            self._step()

    async def fetch(self) -> list[Item]:
        await asyncio.sleep(0)  # a real source awaits network I/O here
        return self._step()

    def _step(self) -> list[Item]:
        items = []
        for k in self._keys:
            prev = self._vals[k]
            self._vals[k] = max(1.0, prev * (1 + self._rng.uniform(-0.02, 0.02)))
            self._hist[k] = (self._hist[k] + [self._vals[k]])[-60:]
            chg = (self._vals[k] - prev) / prev * 100
            status = "down" if chg < -1.5 else "warn" if chg < -0.5 else "ok"
            items.append(Item(k, k, self._vals[k], chg, status))
        return items

    def history(self, key: str) -> list[float]:
        return list(self._hist.get(key, []))
