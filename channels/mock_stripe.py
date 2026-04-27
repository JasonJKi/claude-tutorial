from __future__ import annotations

from core.models import MetricSample, Variant

from .base import Channel, deterministic_noise


class MockStripeChannel(Channel):
    """Simulates Stripe: new subscriptions, MRR, churn for a paywalled tool page."""

    name = "stripe"

    def __init__(self, seed: int = 0, price: float = 9.0):
        self.seed = seed
        self.price = price

    def publish(self, variant: Variant) -> str:
        return f"stripe:price_{variant.spec.get('slug', variant.id)}"

    def unpublish(self, variant: Variant) -> None:
        return None

    def fetch_metrics(self, variant: Variant, tick: int) -> list[MetricSample]:
        quality = float(variant.spec.get("intrinsic_quality", 0.5))
        paywall = float(variant.spec.get("paywall_aggressiveness", 0.5))

        from .mock_analytics import MockAnalyticsChannel
        analytics = MockAnalyticsChannel(seed=self.seed)
        sessions_sample = next(
            s for s in analytics.fetch_metrics(variant, tick) if s.name == "sessions"
        )
        sessions = sessions_sample.value

        # Conversion to paid is multiplicative in quality and paywall pressure.
        new_subs = sessions * 0.01 * paywall * (0.3 + 0.7 * quality) * deterministic_noise(
            self.seed, variant.id or 0, self.name, tick, "new_subs"
        )
        mrr_delta = new_subs * self.price
        # 5% per-tick churn baseline, modulated by inverse of quality.
        churn_rate = 0.05 * (1.5 - quality) * deterministic_noise(
            self.seed, variant.id or 0, self.name, tick, "churn"
        )

        return [
            MetricSample(id=None, variant_id=variant.id, channel=self.name,
                         name="new_subs", value=round(new_subs, 2), tick=tick),
            MetricSample(id=None, variant_id=variant.id, channel=self.name,
                         name="mrr_delta", value=round(mrr_delta, 2), tick=tick),
            MetricSample(id=None, variant_id=variant.id, channel=self.name,
                         name="churn_rate", value=round(churn_rate, 4), tick=tick),
        ]
