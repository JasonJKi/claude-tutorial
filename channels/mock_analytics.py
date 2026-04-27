from __future__ import annotations

from core.models import MetricSample, Variant

from .base import Channel, deterministic_noise


class MockAnalyticsChannel(Channel):
    """Simulates Plausible/PostHog: sessions and email signups derived from SEO clicks."""

    name = "analytics"

    def __init__(self, seo_channel_name: str = "seo", seed: int = 0):
        self.seo_channel_name = seo_channel_name
        self.seed = seed

    def publish(self, variant: Variant) -> str:
        return f"analytics:{variant.spec.get('slug', variant.id)}"

    def unpublish(self, variant: Variant) -> None:
        return None

    def fetch_metrics(self, variant: Variant, tick: int) -> list[MetricSample]:
        quality = float(variant.spec.get("intrinsic_quality", 0.5))
        paywall = float(variant.spec.get("paywall_aggressiveness", 0.5))
        # Approximate sessions from a fresh recompute of clicks (mirrors SEO model
        # so this channel is independently testable without DB access).
        from .mock_seo import MockSEOChannel
        seo = MockSEOChannel(seed=self.seed)
        clicks_sample = next(
            s for s in seo.fetch_metrics(variant, tick) if s.name == "clicks"
        )
        clicks = clicks_sample.value

        sessions = clicks * 1.1 * deterministic_noise(
            self.seed, variant.id or 0, self.name, tick, "sessions"
        )
        # Aggressive paywalls suppress signups; weak paywalls let more emails through.
        signups = sessions * 0.05 * (1.0 - 0.5 * paywall) * deterministic_noise(
            self.seed, variant.id or 0, self.name, tick, "signups"
        )
        # Quality drives engagement (avg session duration in seconds).
        avg_session_sec = (30.0 + 90.0 * quality) * deterministic_noise(
            self.seed, variant.id or 0, self.name, tick, "duration"
        )

        return [
            MetricSample(id=None, variant_id=variant.id, channel=self.name,
                         name="sessions", value=round(sessions, 2), tick=tick),
            MetricSample(id=None, variant_id=variant.id, channel=self.name,
                         name="email_signups", value=round(signups, 2), tick=tick),
            MetricSample(id=None, variant_id=variant.id, channel=self.name,
                         name="avg_session_sec", value=round(avg_session_sec, 2), tick=tick),
        ]
