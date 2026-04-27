from __future__ import annotations

from typing import Any


# Tuned for the simulated traffic levels in mock_seo/analytics/stripe.
# In a real deployment these would be set per venture from real revenue data.
DEFAULT_KILL_MAX_CLICKS_PER_TICK = 1.0
DEFAULT_SCALE_MIN_MRR_DELTA = 0.2
DEFAULT_MAX_VARIANT_SCALE = 4.0
DEFAULT_MIN_AGE_BEFORE_KILL = 3
DEFAULT_DECISION_WINDOW_TICKS = 3


def venture_defaults() -> dict[str, Any]:
    return {
        "budget": 100.0,
        "max_active_variants": 8,
        "kill_max_clicks_per_tick": DEFAULT_KILL_MAX_CLICKS_PER_TICK,
        "scale_min_mrr_delta": DEFAULT_SCALE_MIN_MRR_DELTA,
        "max_variant_scale": DEFAULT_MAX_VARIANT_SCALE,
        "min_age_before_kill": DEFAULT_MIN_AGE_BEFORE_KILL,
        "decision_window_ticks": DEFAULT_DECISION_WINDOW_TICKS,
    }
