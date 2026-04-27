from __future__ import annotations

from pathlib import Path

from channels.mock_analytics import MockAnalyticsChannel
from channels.mock_deploy import MockDeployChannel
from channels.mock_seo import MockSEOChannel
from channels.mock_stripe import MockStripeChannel
from core.models import Variant, VariantStatus


def _variant(quality: float, paywall: float = 0.5, scale: float = 1.0,
             vid: int = 1, slug: str = "json-to-csv") -> Variant:
    return Variant(
        id=vid,
        venture_id=1,
        spec={
            "slug": slug,
            "title": slug,
            "intrinsic_quality": quality,
            "paywall_aggressiveness": paywall,
            "launched_at_tick": 0,
        },
        status=VariantStatus.ACTIVE,
        scale=scale,
    )


def test_seo_deterministic_for_seed() -> None:
    a = MockSEOChannel(seed=42).fetch_metrics(_variant(0.7), tick=3)
    b = MockSEOChannel(seed=42).fetch_metrics(_variant(0.7), tick=3)
    assert [(s.name, s.value) for s in a] == [(s.name, s.value) for s in b]


def test_seo_quality_dominates_impressions() -> None:
    high = MockSEOChannel(seed=1).fetch_metrics(_variant(0.9, vid=1), tick=5)
    low = MockSEOChannel(seed=1).fetch_metrics(_variant(0.1, vid=2), tick=5)
    high_imp = next(s.value for s in high if s.name == "impressions")
    low_imp = next(s.value for s in low if s.name == "impressions")
    assert high_imp > low_imp * 3


def test_seo_age_boost_compounds() -> None:
    early = MockSEOChannel(seed=1).fetch_metrics(_variant(0.5), tick=1)
    later = MockSEOChannel(seed=1).fetch_metrics(_variant(0.5), tick=10)
    early_imp = next(s.value for s in early if s.name == "impressions")
    later_imp = next(s.value for s in later if s.name == "impressions")
    assert later_imp > early_imp


def test_analytics_signups_inverse_to_paywall() -> None:
    soft = MockAnalyticsChannel(seed=7).fetch_metrics(
        _variant(0.6, paywall=0.1, vid=1), tick=4
    )
    hard = MockAnalyticsChannel(seed=7).fetch_metrics(
        _variant(0.6, paywall=0.9, vid=2), tick=4
    )
    soft_signups = next(s.value for s in soft if s.name == "email_signups")
    hard_signups = next(s.value for s in hard if s.name == "email_signups")
    assert soft_signups > hard_signups


def test_stripe_revenue_scales_with_paywall_and_quality() -> None:
    weak = MockStripeChannel(seed=11).fetch_metrics(
        _variant(0.2, paywall=0.2, vid=1), tick=5
    )
    strong = MockStripeChannel(seed=11).fetch_metrics(
        _variant(0.9, paywall=0.7, vid=2), tick=5
    )
    weak_rev = next(s.value for s in weak if s.name == "mrr_delta")
    strong_rev = next(s.value for s in strong if s.name == "mrr_delta")
    assert strong_rev > weak_rev * 5


def test_deploy_writes_and_removes_file(tmp_path: Path) -> None:
    deploy = MockDeployChannel(site_dir=tmp_path)
    v = _variant(0.5, slug="json-to-csv")
    v.spec["html"] = "<h1>JSON to CSV</h1>"
    path = Path(deploy.publish(v))
    assert path.exists()
    assert "JSON to CSV" in path.read_text()

    deploy.unpublish(v)
    assert not path.exists()


def test_deploy_emits_no_metrics() -> None:
    deploy = MockDeployChannel(site_dir="_test_site")
    assert deploy.fetch_metrics(_variant(0.5), tick=1) == []
