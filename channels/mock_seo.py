from __future__ import annotations

from core.models import MetricSample, Variant

from .base import Channel, deterministic_noise


class MockSEOChannel(Channel):
    """Simulates Google Search Console: impressions, clicks, average position."""

    name = "seo"

    def __init__(self, seed: int = 0, base_impressions: float = 50.0):
        self.seed = seed
        self.base_impressions = base_impressions

    def publish(self, variant: Variant) -> str:
        return f"seo:{variant.spec.get('slug', variant.id)}"

    def unpublish(self, variant: Variant) -> None:
        return None

    def fetch_metrics(self, variant: Variant, tick: int) -> list[MetricSample]:
        quality = float(variant.spec.get("intrinsic_quality", 0.5))
        age = max(1, tick - int(variant.spec.get("launched_at_tick", tick)) + 1)
        # SEO compounds with age (indexing, backlinks, freshness signals).
        age_boost = 1.0 + min(age * 0.1, 1.5)

        impressions = (
            self.base_impressions
            * quality
            * variant.scale
            * age_boost
            * deterministic_noise(self.seed, variant.id or 0, self.name, tick, "impressions")
        )
        ctr = 0.05 + 0.10 * quality
        clicks = impressions * ctr * deterministic_noise(
            self.seed, variant.id or 0, self.name, tick, "clicks"
        )
        # Lower position number = better rank.
        position = max(1.0, 30.0 - 25.0 * quality) * deterministic_noise(
            self.seed, variant.id or 0, self.name, tick, "position"
        )

        return [
            MetricSample(id=None, variant_id=variant.id, channel=self.name,
                         name="impressions", value=round(impressions, 2), tick=tick),
            MetricSample(id=None, variant_id=variant.id, channel=self.name,
                         name="clicks", value=round(clicks, 2), tick=tick),
            MetricSample(id=None, variant_id=variant.id, channel=self.name,
                         name="avg_position", value=round(position, 2), tick=tick),
        ]
