from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

from core.models import MetricSample, Variant


class Channel(ABC):
    name: str

    @abstractmethod
    def publish(self, variant: Variant) -> str:
        """Publish the variant to this channel; return the channel-side id."""

    @abstractmethod
    def unpublish(self, variant: Variant) -> None:
        """Tear down the variant on this channel (called on KILL)."""

    @abstractmethod
    def fetch_metrics(self, variant: Variant, tick: int) -> list[MetricSample]:
        """Return the metric samples produced for this variant at this tick."""


def deterministic_noise(
    seed: int, variant_id: int, channel: str, tick: int, name: str
) -> float:
    """Returns a stable multiplier in [0.9, 1.1] for (seed, variant, channel, tick, metric)."""
    key = f"{seed}|{variant_id}|{channel}|{tick}|{name}".encode()
    digest = hashlib.md5(key).digest()
    val = int.from_bytes(digest[:4], "big")
    return 0.9 + (val / 0xFFFFFFFF) * 0.2
